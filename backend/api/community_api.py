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
from storage.supabase_bookmarks import SupabaseBookmarkError, configured_supabase_bookmark_repository
from storage.supabase_comments import SupabaseCommentError, configured_supabase_comment_repository
from storage.supabase_posts import SupabasePostError, configured_supabase_post_repository
from storage.supabase_reactions import SupabaseReactionError, configured_supabase_reaction_repository
from storage.supabase_storage import SupabaseStorageError, configured_supabase_storage_client


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


def _normalize_preview_type(value: str) -> str:
    if value not in VALID_PREVIEW_TYPES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PREVIEW_TYPE", "message": "Invalid preview type"})
    return value


def _tone_for_user(user_id: int) -> str:
    tones = ["aqua", "amber", "green", "rose", "indigo", "blue"]
    return tones[user_id % len(tones)]


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
    return comments if comments else None


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

    post = db.insert_community_post(
        {
            "user_id": int(user["id"]),
            "author_name": user["username"],
            "badge": "玩家",
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
    try:
        post = db.toggle_community_like(post_id, int(user["id"]))
        _sync_supabase_post_reaction(post_id, int(user["id"]), bool(post["liked_by_me"]))
        return post
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.post("/api/community/posts/{post_id}/bookmark")
async def toggle_community_bookmark(post_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    try:
        post = db.toggle_community_bookmark(post_id, int(user["id"]))
        _sync_supabase_post_bookmark(post_id, int(user["id"]), bool(post["bookmarked_by_me"]))
        return post
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.get("/api/community/posts/{post_id}/comments")
async def get_community_comments(post_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _optional_user(authorization)
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
    body = request.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "Comment body is required"})

    try:
        comment = db.insert_community_comment(post_id, int(user["id"]), user["username"], body)
        _sync_supabase_community_comment(comment)
        post = db.get_community_post(post_id, int(user["id"]))
        return JSONResponse({"comment": comment, "post": post}, status_code=201)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.post("/api/community/comments/{comment_id}/like")
async def toggle_community_comment_like(comment_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    try:
        comment = db.toggle_community_comment_like(comment_id, int(user["id"]))
        _sync_supabase_comment_reaction(comment_id, int(user["id"]), bool(comment["liked_by_me"]))
        return comment
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "COMMENT_NOT_FOUND", "message": "Comment not found"}) from exc
