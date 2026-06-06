import os
import base64
import binascii
import re
import sys
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth.account_store import AccountStore
from auth.account_store_factory import create_account_store
from database.database import Database
from storage.supabase_accounts import SupabaseAccountError
from storage.supabase_blocks import SupabaseBlockError, configured_supabase_block_repository
from storage.supabase_bookmarks import SupabaseBookmarkError, configured_supabase_bookmark_repository
from storage.supabase_comments import SupabaseCommentError, configured_supabase_comment_repository
from storage.supabase_posts import SupabasePostError, configured_supabase_post_repository
from storage.supabase_reactions import SupabaseReactionError, configured_supabase_reaction_repository
from storage.supabase_storage import SupabaseStorageError, configured_supabase_storage_client
from services.mobile_push_notifications import MobilePushEvent, configured_mobile_push_notification_service


db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
account_store = create_account_store(db_path)
db = Database(db_path)
router = APIRouter()

VALID_PREVIEW_TYPES = {"pool-table", "pool-table-alt", "pose-analysis", "stats"}
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "community_uploads")
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


class CommunityPostRequest(BaseModel):
    title: str = Field("", max_length=80)
    body: str = Field("", max_length=800)
    preview_type: str = "pool-table"
    recording_id: Optional[str] = None
    image_urls: list[str] = Field(default_factory=list, max_length=3)
    image_transforms: list[dict[str, float]] = Field(default_factory=list, max_length=3)


class CommunityUploadImage(BaseModel):
    filename: str = Field("", max_length=120)
    mime_type: str = Field("image/jpeg", max_length=40)
    data: str = Field(..., min_length=1)


class CommunityUploadRequest(BaseModel):
    images: list[CommunityUploadImage] = Field(..., min_length=1, max_length=3)
    purpose: str = Field("post", pattern="^(post|avatar)$")


class CommunityCommentRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=500)


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization[7:].strip()


def _current_user(authorization: str | None) -> dict:
    token = _extract_token(authorization)
    try:
        user = account_store.authenticate_token(token)
    except SupabaseAccountError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "ACCOUNT_STORE_ERROR", "message": str(exc)},
        ) from exc
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    return user


def _optional_user(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    try:
        return _current_user(authorization)
    except HTTPException:
        return None


def _has_block_between(user_a_id: int, user_b_id: int) -> bool:
    if int(user_a_id) == int(user_b_id):
        return False
    repo = configured_supabase_block_repository()
    if repo is None:
        return db.has_block_between_users(int(user_a_id), int(user_b_id))
    try:
        return repo.has_block_between(int(user_a_id), int(user_b_id))
    except SupabaseBlockError as exc:
        print(f"WARNING Supabase block state read failed; using local block state: {exc}")
        return db.has_block_between_users(int(user_a_id), int(user_b_id))


def _filter_blocked_posts(posts: list[dict], viewer_user_id: int | None) -> list[dict]:
    if viewer_user_id is None:
        return posts
    visible_posts: list[dict] = []
    for post in posts:
        author_user_id = post.get("user_id")
        if author_user_id is None:
            visible_posts.append(post)
            continue
        try:
            author_id = int(author_user_id)
        except (TypeError, ValueError):
            visible_posts.append(post)
            continue
        if not _has_block_between(int(viewer_user_id), author_id):
            visible_posts.append(post)
    return visible_posts


def _dispatch_mobile_push_notification(event: MobilePushEvent) -> None:
    service = configured_mobile_push_notification_service()
    if service is None:
        return
    try:
        service.dispatch(event)
    except Exception as exc:
        print(f"WARNING mobile push notification dispatch failed: {exc}")


def _actor_display_name(user: dict) -> str:
    return str(user.get("display_name") or user.get("username") or "使用者")


def _normalize_preview_type(value: str) -> str:
    if value not in VALID_PREVIEW_TYPES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PREVIEW_TYPE", "message": "Invalid preview type"})
    return value


def _tone_for_user(user_id: int) -> str:
    tones = ["aqua", "amber", "green", "rose", "indigo", "blue"]
    return tones[user_id % len(tones)]


def _is_official_user(user: dict) -> bool:
    username = str(user.get("username") or "").strip().casefold()
    display_name = str(user.get("display_name") or "").strip().casefold()
    return username == "cuevex" or display_name in {"cuevex", "cuevex 官方"}


def _badge_for_user(user: dict) -> str:
    return "官方帳號" if _is_official_user(user) else "玩家"


def _normalize_image_urls(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()][:3]


def _extension_for_mime_type(mime_type: str) -> str:
    normalized = mime_type.lower().split(";")[0].strip()
    if normalized == "image/png":
        return ".png"
    if normalized == "image/webp":
        return ".webp"
    if normalized in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE_TYPE", "message": "Only jpeg, png and webp images are supported."})


def _decode_image_data(data: str) -> bytes:
    payload = re.sub(r"^data:image/[a-zA-Z0-9.+-]+;base64,", "", data.strip())
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE_DATA", "message": "Image data must be base64."}) from exc
    if not decoded or len(decoded) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail={"code": "IMAGE_TOO_LARGE", "message": "單張照片需小於 15MB，請換一張較小的照片。"})
    return decoded


def _storage_object_path(user_id: int, purpose: str, extension: str) -> str:
    folder = "avatars" if purpose == "avatar" else "posts"
    safe_extension = extension if extension.startswith(".") else f".{extension}"
    return f"users/{user_id}/{folder}/{uuid.uuid4().hex}{safe_extension}"


def _save_local_upload(user_id: int, extension: str, content: bytes) -> str:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"user{user_id}_{uuid.uuid4().hex}{extension}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as file:
        file.write(content)
    return f"/api/community/uploads/{filename}"


def _save_upload(user_id: int, purpose: str, extension: str, mime_type: str, content: bytes) -> str:
    supabase_client = configured_supabase_storage_client()
    if supabase_client is not None:
        object_path = _storage_object_path(user_id, purpose, extension)
        try:
            return supabase_client.upload_public_object(object_path, content, mime_type)
        except SupabaseStorageError as exc:
            print(f"WARNING Supabase upload failed; falling back to local storage: {exc}")
    return _save_local_upload(user_id, extension, content)


def _sync_supabase_community_post(post: dict) -> None:
    repo = configured_supabase_post_repository()
    if repo is None:
        return
    try:
        repo.upsert_post(post)
    except SupabasePostError as exc:
        print(f"WARNING Supabase post sync failed; local post remains active: {exc}")


def _delete_supabase_community_post(post_id: int) -> None:
    repo = configured_supabase_post_repository()
    if repo is None:
        return
    try:
        repo.delete_post(post_id)
    except SupabasePostError as exc:
        print(f"WARNING Supabase post delete failed; local delete remains active: {exc}")


def _sync_supabase_community_comment(comment: dict) -> None:
    repo = configured_supabase_comment_repository()
    if repo is None:
        return
    try:
        repo.upsert_comment(comment)
    except SupabaseCommentError as exc:
        print(f"WARNING Supabase comment sync failed; local comment remains active: {exc}")


def _sync_supabase_post_reaction(post_id: int, user_id: int, liked: bool) -> None:
    repo = configured_supabase_reaction_repository()
    if repo is None:
        return
    try:
        repo.set_post_reaction(post_id, user_id, liked)
    except SupabaseReactionError as exc:
        print(f"WARNING Supabase post reaction sync failed; local reaction remains active: {exc}")


def _sync_supabase_comment_reaction(comment_id: int, user_id: int, liked: bool) -> None:
    repo = configured_supabase_reaction_repository()
    if repo is None:
        return
    try:
        repo.set_comment_reaction(comment_id, user_id, liked)
    except SupabaseReactionError as exc:
        print(f"WARNING Supabase comment reaction sync failed; local reaction remains active: {exc}")


def _sync_supabase_post_bookmark(post_id: int, user_id: int, bookmarked: bool) -> None:
    repo = configured_supabase_bookmark_repository()
    if repo is None:
        return
    try:
        repo.set_post_bookmark(post_id, user_id, bookmarked)
    except SupabaseBookmarkError as exc:
        print(f"WARNING Supabase post bookmark sync failed; local bookmark remains active: {exc}")


def _get_comments_from_supabase(post_id: int, viewer_user_id: int | None) -> list[dict] | None:
    repo = configured_supabase_comment_repository()
    if repo is None:
        return None
    try:
        comments = repo.list_comments_for_post(post_id, viewer_user_id)
    except SupabaseCommentError as exc:
        print(f"WARNING Supabase comments read failed; using local comments: {exc}")
        return None
    return comments


def _create_post_in_supabase(user: dict, request: CommunityPostRequest, title: str, body: str, image_urls: list[str], image_transforms: list[dict[str, float]]) -> dict | None:
    repo = configured_supabase_post_repository()
    if repo is None:
        return None
    if not hasattr(repo, "create_post"):
        return None
    try:
        post = repo.create_post(
            {
                "user_id": int(user["id"]),
                "author_name": user["username"],
                "badge": _badge_for_user(user),
                "title": title,
                "body": body,
                "image_urls": image_urls,
                "image_transforms": image_transforms,
                "preview_type": _normalize_preview_type(request.preview_type),
                "recording_id": request.recording_id,
                "tone": _tone_for_user(int(user["id"])),
            },
            viewer_user_id=int(user["id"]),
        )
        if not post.get("author_avatar_url") and user.get("avatar_url"):
            post["author_avatar_url"] = str(user.get("avatar_url") or "")
        return post
    except SupabasePostError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_POST_FAILED", "message": str(exc)}) from exc


def _get_post_from_supabase(post_id: int, viewer_user_id: int) -> dict | None:
    repo = configured_supabase_post_repository()
    if repo is None:
        return None
    if not hasattr(repo, "get_post"):
        return None
    try:
        return repo.get_post(post_id, viewer_user_id)
    except SupabasePostError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_POST_FAILED", "message": str(exc)}) from exc


def _ensure_post_visible_to_user(post_id: int, viewer_user_id: int) -> None:
    post = _get_post_from_supabase(post_id, viewer_user_id)
    if post is None:
        post = db.get_community_post(post_id, viewer_user_id)
    if post is None:
        return
    author_user_id = post.get("user_id")
    if author_user_id is None:
        return
    if _has_block_between(int(viewer_user_id), int(author_user_id)):
        raise HTTPException(status_code=403, detail={"code": "USER_BLOCKED", "message": "Blocked users cannot interact with this post."})


def _ensure_comment_visible_to_user(comment_id: int, viewer_user_id: int) -> None:
    comment_repo = configured_supabase_comment_repository()
    if comment_repo is not None and hasattr(comment_repo, "get_comment"):
        try:
            comment = comment_repo.get_comment(comment_id, viewer_user_id)
        except SupabaseCommentError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_COMMENT_FAILED", "message": str(exc)}) from exc
        if comment is not None:
            _ensure_post_visible_to_user(int(comment["post_id"]), viewer_user_id)
            return
    with db.transaction() as conn:
        row = conn.execute("SELECT post_id FROM community_comments WHERE id = ?", (comment_id,)).fetchone()
    if row is not None:
        _ensure_post_visible_to_user(int(row["post_id"]), viewer_user_id)


def _create_comment_in_supabase(post_id: int, user: dict, body: str) -> tuple[dict, dict] | None:
    comment_repo = configured_supabase_comment_repository()
    post_repo = configured_supabase_post_repository()
    if comment_repo is None or post_repo is None:
        return None
    if not hasattr(comment_repo, "create_comment") or not hasattr(post_repo, "get_post"):
        return None
    try:
        if hasattr(comment_repo, "create_comment_rpc"):
            rpc_result = comment_repo.create_comment_rpc(post_id, int(user["id"]), body)
            if rpc_result is not None and isinstance(rpc_result.get("comment"), dict) and isinstance(rpc_result.get("post"), dict):
                return rpc_result["comment"], rpc_result["post"]
        post = post_repo.get_post(post_id, int(user["id"]))
        if post is None:
            raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"})
        comment = comment_repo.create_comment(
            {
                "post_id": post_id,
                "user_id": int(user["id"]),
                "author_name": user["username"],
                "body": body,
            },
            viewer_user_id=int(user["id"]),
        )
        if not comment.get("author_avatar_url") and user.get("avatar_url"):
            comment["author_avatar_url"] = str(user.get("avatar_url") or "")
        updated_post = post_repo.get_post(post_id, int(user["id"])) or post
        return comment, updated_post
    except SupabaseCommentError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_COMMENT_FAILED", "message": str(exc)}) from exc
    except SupabasePostError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_POST_FAILED", "message": str(exc)}) from exc


def _toggle_post_like_in_supabase(post_id: int, user_id: int) -> dict | None:
    post_repo = configured_supabase_post_repository()
    reaction_repo = configured_supabase_reaction_repository()
    if post_repo is None:
        return None
    if hasattr(post_repo, "toggle_post_like"):
        try:
            rpc_post = post_repo.toggle_post_like(post_id, user_id)
            if rpc_post is not None:
                return rpc_post
        except SupabasePostError as exc:
            print(f"WARNING Supabase toggle like RPC failed; using legacy flow: {exc}")
    if reaction_repo is None:
        return None
    if not hasattr(post_repo, "get_post"):
        return None
    try:
        post = post_repo.get_post(post_id, user_id)
        if post is None:
            raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"})
        liked = not bool(post.get("liked_by_me"))
        reaction_repo.set_post_reaction(post_id, user_id, liked)
        return post_repo.get_post(post_id, user_id) or post
    except SupabaseReactionError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_REACTION_FAILED", "message": str(exc)}) from exc
    except SupabasePostError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_POST_FAILED", "message": str(exc)}) from exc


def _toggle_post_bookmark_in_supabase(post_id: int, user_id: int) -> dict | None:
    post_repo = configured_supabase_post_repository()
    bookmark_repo = configured_supabase_bookmark_repository()
    if post_repo is None:
        return None
    if hasattr(post_repo, "toggle_post_bookmark"):
        try:
            rpc_post = post_repo.toggle_post_bookmark(post_id, user_id)
            if rpc_post is not None:
                return rpc_post
        except SupabasePostError as exc:
            print(f"WARNING Supabase toggle bookmark RPC failed; using legacy flow: {exc}")
    if bookmark_repo is None:
        return None
    if not hasattr(post_repo, "get_post"):
        return None
    try:
        post = post_repo.get_post(post_id, user_id)
        if post is None:
            raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"})
        bookmarked = not bool(post.get("bookmarked_by_me"))
        bookmark_repo.set_post_bookmark(post_id, user_id, bookmarked)
        return post_repo.get_post(post_id, user_id) or post
    except SupabaseBookmarkError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_BOOKMARK_FAILED", "message": str(exc)}) from exc
    except SupabasePostError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_POST_FAILED", "message": str(exc)}) from exc


def _get_bookmarked_posts_from_supabase(user_id: int, limit: int, offset: int) -> tuple[list[dict], int] | None:
    post_repo = configured_supabase_post_repository()
    bookmark_repo = configured_supabase_bookmark_repository()
    if post_repo is None:
        return None
    if hasattr(post_repo, "list_bookmarked_posts"):
        try:
            rpc_bookmarks = post_repo.list_bookmarked_posts(user_id, limit=limit, offset=offset)
            if rpc_bookmarks is not None:
                return rpc_bookmarks
        except SupabasePostError as exc:
            print(f"WARNING Supabase bookmarked posts RPC failed; using legacy flow: {exc}")
    if bookmark_repo is None:
        return None
    if not hasattr(bookmark_repo, "list_bookmarked_post_refs") or not hasattr(post_repo, "list_posts_by_ids"):
        return None
    try:
        refs, total = bookmark_repo.list_bookmarked_post_refs(user_id, limit, offset)
        post_ids = [int(ref["post_id"]) for ref in refs if ref.get("post_id") is not None]
        posts = post_repo.list_posts_by_ids(post_ids, viewer_user_id=user_id)
        return posts, total
    except SupabaseBookmarkError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_BOOKMARK_FAILED", "message": str(exc)}) from exc
    except SupabasePostError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_POST_FAILED", "message": str(exc)}) from exc


def _toggle_comment_like_in_supabase(comment_id: int, user_id: int) -> dict | None:
    comment_repo = configured_supabase_comment_repository()
    reaction_repo = configured_supabase_reaction_repository()
    if comment_repo is None:
        return None
    if hasattr(comment_repo, "toggle_comment_like"):
        try:
            rpc_comment = comment_repo.toggle_comment_like(comment_id, user_id)
            if rpc_comment is not None:
                return rpc_comment
        except SupabaseCommentError as exc:
            print(f"WARNING Supabase toggle comment like RPC failed; using legacy flow: {exc}")
    if reaction_repo is None:
        return None
    if not hasattr(comment_repo, "get_comment"):
        return None
    try:
        comment = comment_repo.get_comment(comment_id, user_id)
        if comment is None:
            raise HTTPException(status_code=404, detail={"code": "COMMENT_NOT_FOUND", "message": "Comment not found"})
        liked = not bool(comment.get("liked_by_me"))
        reaction_repo.set_comment_reaction(comment_id, user_id, liked)
        return comment_repo.get_comment(comment_id, user_id) or comment
    except SupabaseReactionError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_REACTION_FAILED", "message": str(exc)}) from exc
    except SupabaseCommentError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_COMMENT_FAILED", "message": str(exc)}) from exc


@router.get("/api/community/posts")
async def get_community_posts(
    authorization: Annotated[str | None, Header()] = None,
    tab: str = Query("all", pattern="^(all|explore|following)$"),
    sort: str = Query("latest", pattern="^(latest|popular|comments)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    user = _optional_user(authorization)
    try:
        posts, total = db.get_community_posts(
            tab=tab,
            sort=sort,
            limit=limit,
            offset=offset,
            viewer_user_id=int(user["id"]) if user else None,
        )
        posts = _filter_blocked_posts(posts, int(user["id"]) if user else None)
        return {"posts": posts, "total": total, "limit": limit, "offset": offset}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": str(exc)}) from exc


@router.get("/api/community/uploads/{filename}")
async def get_community_upload(filename: str):
    safe_name = os.path.basename(filename)
    path = os.path.abspath(os.path.join(UPLOAD_DIR, safe_name))
    if not path.startswith(os.path.abspath(UPLOAD_DIR)) or not os.path.exists(path):
        raise HTTPException(status_code=404, detail={"code": "UPLOAD_NOT_FOUND", "message": "Upload not found"})
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.post("/api/community/uploads")
async def upload_community_images(
    request: Annotated[CommunityUploadRequest, Body(...)],
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    urls: list[str] = []
    for image in request.images:
        extension = _extension_for_mime_type(image.mime_type)
        content = _decode_image_data(image.data)
        urls.append(_save_upload(int(user["id"]), request.purpose, extension, image.mime_type, content))
    return {"image_urls": urls}


@router.post("/api/community/posts")
async def create_community_post(
    request: Annotated[CommunityPostRequest, Body(...)],
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    title = request.title.strip()
    body = request.body.strip()
    image_urls = _normalize_image_urls(request.image_urls)
    image_transforms = request.image_transforms[: len(image_urls)]
    if not body and not image_urls:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "Body or image is required"})

    supabase_post = _create_post_in_supabase(user, request, title, body, image_urls, image_transforms)
    if supabase_post is not None:
        return JSONResponse(supabase_post, status_code=201)

    post = db.insert_community_post(
        {
            "user_id": int(user["id"]),
            "author_name": user["username"],
            "badge": _badge_for_user(user),
            "title": title,
            "body": body,
            "image_urls": image_urls,
            "image_transforms": image_transforms,
            "preview_type": _normalize_preview_type(request.preview_type),
            "recording_id": request.recording_id,
            "tone": _tone_for_user(int(user["id"])),
        }
    )
    _sync_supabase_community_post(post)
    return JSONResponse(post, status_code=201)


@router.delete("/api/community/posts/{post_id}")
async def delete_community_post(post_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    supabase_post = _get_post_from_supabase(post_id, int(user["id"]))
    if supabase_post is not None:
        if int(supabase_post.get("user_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Only the author can delete this post"})
        _delete_supabase_community_post(post_id)
        return {"status": "deleted", "post_id": post_id}

    try:
        deleted = db.delete_community_post(post_id, int(user["id"]))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc
    if not deleted:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Only the author can delete this post"})
    _delete_supabase_community_post(post_id)
    return {"status": "deleted", "post_id": post_id}


@router.post("/api/community/posts/{post_id}/like")
async def toggle_community_like(post_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    supabase_post = _toggle_post_like_in_supabase(post_id, int(user["id"]))
    if supabase_post is not None:
        if bool(supabase_post.get("liked_by_me")) and int(supabase_post.get("user_id") or 0) != int(user["id"]):
            _dispatch_mobile_push_notification(MobilePushEvent(
                recipient_user_id=int(supabase_post.get("user_id") or 0),
                actor_user_id=int(user["id"]),
                event_type="post_liked",
                source_type="post",
                source_id=int(post_id),
                title="有人按讚你的貼文",
                body=f"{_actor_display_name(user)} 按讚了你的貼文",
                data={"post_id": int(post_id)},
            ))
        return supabase_post
    _ensure_post_visible_to_user(post_id, int(user["id"]))

    try:
        post = db.toggle_community_like(post_id, int(user["id"]))
        _sync_supabase_post_reaction(post_id, int(user["id"]), bool(post["liked_by_me"]))
        if bool(post.get("liked_by_me")) and int(post.get("user_id") or 0) != int(user["id"]):
            _dispatch_mobile_push_notification(MobilePushEvent(
                recipient_user_id=int(post.get("user_id") or 0),
                actor_user_id=int(user["id"]),
                event_type="post_liked",
                source_type="post",
                source_id=int(post_id),
                title="有人按讚你的貼文",
                body=f"{_actor_display_name(user)} 按讚了你的貼文",
                data={"post_id": int(post_id)},
            ))
        return post
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.post("/api/community/posts/{post_id}/bookmark")
async def toggle_community_bookmark(post_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    supabase_post = _toggle_post_bookmark_in_supabase(post_id, int(user["id"]))
    if supabase_post is not None:
        return supabase_post
    _ensure_post_visible_to_user(post_id, int(user["id"]))

    try:
        post = db.toggle_community_bookmark(post_id, int(user["id"]))
        _sync_supabase_post_bookmark(post_id, int(user["id"]), bool(post["bookmarked_by_me"]))
        return post
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.get("/api/community/bookmarks")
async def get_community_bookmarks(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    user = _current_user(authorization)
    supabase_bookmarks = _get_bookmarked_posts_from_supabase(int(user["id"]), limit, offset)
    if supabase_bookmarks is None:
        posts, total = db.get_bookmarked_community_posts(int(user["id"]), limit=limit, offset=offset)
    else:
        posts, total = supabase_bookmarks
    posts = _filter_blocked_posts(posts, int(user["id"]))
    return {"posts": posts, "total": total, "limit": limit, "offset": offset}


@router.get("/api/community/posts/{post_id}/comments")
async def get_community_comments(post_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _optional_user(authorization)
    if user:
        _ensure_post_visible_to_user(post_id, int(user["id"]))
    try:
        comments = _get_comments_from_supabase(post_id, int(user["id"]) if user else None)
        if comments is None:
            comments = db.get_community_comments(post_id, int(user["id"]) if user else None)
        return {"comments": comments, "total": len(comments)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.post("/api/community/posts/{post_id}/comments")
async def create_community_comment(
    post_id: int,
    request: Annotated[CommunityCommentRequest, Body(...)],
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    _ensure_post_visible_to_user(post_id, int(user["id"]))
    body = request.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "Comment body is required"})

    supabase_result = _create_comment_in_supabase(post_id, user, body)
    if supabase_result is not None:
        comment, post = supabase_result
        if int(post.get("user_id") or 0) != int(user["id"]):
            _dispatch_mobile_push_notification(MobilePushEvent(
                recipient_user_id=int(post.get("user_id") or 0),
                actor_user_id=int(user["id"]),
                event_type="post_commented",
                source_type="post",
                source_id=int(post_id),
                title="有人留言你的貼文",
                body=f"{_actor_display_name(user)} 留言了你的貼文",
                data={"post_id": int(post_id), "comment_id": int(comment.get("id") or 0)},
            ))
        return JSONResponse({"comment": comment, "post": post}, status_code=201)

    try:
        comment = db.insert_community_comment(post_id, int(user["id"]), user["username"], body)
        _sync_supabase_community_comment(comment)
        post = db.get_community_post(post_id, int(user["id"]))
        if post and int(post.get("user_id") or 0) != int(user["id"]):
            _dispatch_mobile_push_notification(MobilePushEvent(
                recipient_user_id=int(post.get("user_id") or 0),
                actor_user_id=int(user["id"]),
                event_type="post_commented",
                source_type="post",
                source_id=int(post_id),
                title="有人留言你的貼文",
                body=f"{_actor_display_name(user)} 留言了你的貼文",
                data={"post_id": int(post_id), "comment_id": int(comment.get("id") or 0)},
            ))
        return JSONResponse({"comment": comment, "post": post}, status_code=201)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.post("/api/community/comments/{comment_id}/like")
async def toggle_community_comment_like(comment_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    supabase_comment = _toggle_comment_like_in_supabase(comment_id, int(user["id"]))
    if supabase_comment is not None:
        if bool(supabase_comment.get("liked_by_me")) and int(supabase_comment.get("user_id") or 0) != int(user["id"]):
            _dispatch_mobile_push_notification(MobilePushEvent(
                recipient_user_id=int(supabase_comment.get("user_id") or 0),
                actor_user_id=int(user["id"]),
                event_type="comment_liked",
                source_type="comment",
                source_id=int(comment_id),
                title="有人按讚你的留言",
                body=f"{_actor_display_name(user)} 按讚了你的留言",
                data={"post_id": int(supabase_comment.get("post_id") or 0), "comment_id": int(comment_id)},
            ))
        return supabase_comment
    _ensure_comment_visible_to_user(comment_id, int(user["id"]))

    try:
        comment = db.toggle_community_comment_like(comment_id, int(user["id"]))
        _sync_supabase_comment_reaction(comment_id, int(user["id"]), bool(comment["liked_by_me"]))
        if bool(comment.get("liked_by_me")) and int(comment.get("user_id") or 0) != int(user["id"]):
            _dispatch_mobile_push_notification(MobilePushEvent(
                recipient_user_id=int(comment.get("user_id") or 0),
                actor_user_id=int(user["id"]),
                event_type="comment_liked",
                source_type="comment",
                source_id=int(comment_id),
                title="有人按讚你的留言",
                body=f"{_actor_display_name(user)} 按讚了你的留言",
                data={"post_id": int(comment.get("post_id") or 0), "comment_id": int(comment_id)},
            ))
        return comment
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "COMMENT_NOT_FOUND", "message": "Comment not found"}) from exc
