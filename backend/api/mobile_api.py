import os
from typing import Annotated, Any, Awaitable, Callable
from urllib.parse import parse_qs, quote, urlparse

from fastapi import APIRouter, Body, Header, HTTPException, Query
from pydantic import BaseModel

import config
from auth.account_store import AccountError, AccountStore
from database.database import Database
from storage.supabase_profiles import SupabaseProfileError, configured_supabase_profile_repository
from storage.supabase_posts import SupabasePostError, configured_supabase_post_repository


db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
account_store = AccountStore(
    db_path,
    session_ttl_seconds=int(getattr(config, "AUTH_SESSION_TTL_SECONDS", 7 * 24 * 60 * 60)),
)
db = Database(db_path)
router = APIRouter()

StartFriendGameHandler = Callable[[str, str], Awaitable[dict[str, Any]]]
start_friend_game_handler: StartFriendGameHandler | None = None


class FriendInviteRequest(BaseModel):
    base_url: str = ""


class AcceptFriendInviteRequest(BaseModel):
    payload: str


class MobileProfileUpdateRequest(BaseModel):
    display_name: str = ""
    bio: str = ""
    avatar_url: str = ""


def set_start_friend_game_handler(handler: StartFriendGameHandler) -> None:
    global start_friend_game_handler
    start_friend_game_handler = handler


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization[7:].strip()


def _current_user(authorization: str | None) -> dict[str, Any]:
    token = _extract_token(authorization)
    user = account_store.authenticate_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    return user


def _account_error_response(error: AccountError) -> HTTPException:
    status_code = 400
    if error.code == "USER_NOT_FOUND":
        status_code = 404
    if error.code in {"INVALID_FRIEND_INVITE", "FRIEND_INVITE_EXPIRED"}:
        status_code = 400
    if error.code == "FRIEND_REQUIRED":
        status_code = 403
    return HTTPException(status_code=status_code, detail={"code": error.code, "message": error.message})


def _normalize_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    if not base_url:
        return ""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_BASE_URL", "message": "base_url must be http(s)."})
    return base_url


def _resolve_invite_base_url(request_base_url: str) -> str:
    base_url = _normalize_base_url(request_base_url) or _normalize_base_url(
        str(getattr(config, "MOBILE_PUBLIC_BASE_URL", ""))
    )
    if not base_url:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MOBILE_PUBLIC_BASE_URL_REQUIRED",
                "message": "Set MOBILE_PUBLIC_BASE_URL or pass base_url before creating a remote QR invite.",
            },
        )

    parsed = urlparse(base_url)
    if bool(getattr(config, "MOBILE_REQUIRE_HTTPS_QR", False)) and parsed.scheme != "https":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "HTTPS_BASE_URL_REQUIRED",
                "message": "Remote mobile QR invites require an https base_url.",
            },
        )
    return base_url


def _parse_invite_token(payload: str) -> str:
    value = payload.strip()
    if not value:
        raise HTTPException(status_code=400, detail={"code": "INVALID_QR_PAYLOAD", "message": "QR payload is empty."})
    if value.startswith("cuevex://friend-invite"):
        parsed = urlparse(value)
        token = parse_qs(parsed.query).get("token", [""])[0]
        if token:
            return token
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        token = parse_qs(parsed.query).get("token", [""])[0]
        if token:
            return token
    if len(value) >= 32:
        return value
    raise HTTPException(status_code=400, detail={"code": "INVALID_QR_PAYLOAD", "message": "QR payload is not a friend invite."})


def _derive_player_level(analytics: dict[str, Any]) -> str:
    total_games = int(analytics.get("total_games") or 0)
    win_rate = float(analytics.get("win_rate") or 0)
    if total_games >= 60 and win_rate >= 0.6:
        return "進階玩家 II"
    if total_games >= 30:
        return "進階玩家 I"
    if total_games >= 10:
        return "新手玩家 III"
    if total_games > 0:
        return "新手玩家 II"
    return "新手玩家 I"



def _mobile_profile_payload(user: dict[str, Any], viewer_user_id: int | None = None) -> dict[str, Any]:
    profile_user = _merge_supabase_mobile_profile(user)
    analytics = db.get_player_analytics(str(user["username"]))
    display_name = str(profile_user.get("display_name") or "").strip() or str(user.get("username") or "").strip()
    follow_counts = db.get_follow_counts(int(user["id"]))
    payload = {
        "user": profile_user,
        "display_name": display_name,
        "bio": str(profile_user.get("bio") or ""),
        "avatar_url": str(profile_user.get("avatar_url") or ""),
        "player_level": _derive_player_level(analytics),
        "followers_count": follow_counts["followers_count"],
        "following_count": follow_counts["following_count"],
        "post_count": db.count_community_posts_for_user(int(user["id"])),
    }
    if viewer_user_id is not None:
        payload["is_following"] = db.is_following_user(viewer_user_id, int(user["id"]))
        payload["is_self"] = viewer_user_id == int(user["id"])
    return payload


def _merge_supabase_mobile_profile(user: dict[str, Any]) -> dict[str, Any]:
    repo = configured_supabase_profile_repository()
    if repo is None:
        return user
    try:
        profile = repo.get_profile(int(user["id"]))
    except SupabaseProfileError as exc:
        print(f"WARNING Supabase profile read failed; using local profile: {exc}")
        return user
    if not profile:
        return user
    merged = dict(user)
    merged["display_name"] = str(profile.get("display_name") or "")
    merged["bio"] = str(profile.get("bio") or "")
    merged["avatar_url"] = str(profile.get("avatar_url") or "")
    return merged


def _sync_supabase_mobile_profile(user: dict[str, Any]) -> None:
    repo = configured_supabase_profile_repository()
    if repo is None:
        return
    try:
        repo.upsert_profile(
            int(user["id"]),
            str(user.get("display_name") or ""),
            str(user.get("bio") or ""),
            str(user.get("avatar_url") or ""),
        )
    except SupabaseProfileError as exc:
        print(f"WARNING Supabase profile sync failed; local profile remains active: {exc}")


def _get_profile_posts_from_supabase(author_user_id: int, limit: int, offset: int) -> tuple[list[dict[str, Any]], int] | None:
    repo = configured_supabase_post_repository()
    if repo is None:
        return None
    try:
        posts, total = repo.list_posts_for_user(author_user_id, limit=limit, offset=offset)
    except SupabasePostError as exc:
        print(f"WARNING Supabase profile posts read failed; using local posts: {exc}")
        return None
    if not posts and total == 0:
        return None
    return posts, total


def _parse_exclude_ids(value: str) -> list[int]:
    ids: list[int] = []
    for raw_id in value.split(","):
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        try:
            post_id = int(raw_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_EXCLUDE_IDS", "message": "exclude_ids must be comma-separated integers."},
            ) from exc
        if post_id > 0:
            ids.append(post_id)
    return ids


@router.get("/api/mobile/dashboard")
async def get_mobile_dashboard(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    analytics = db.get_player_analytics(str(user["username"]))
    return {
        "user": user,
        "stats": {
            "total_games": analytics["total_games"],
            "total_wins": analytics["total_wins"],
            "win_rate": analytics["win_rate"],
            "total_practice_sessions": analytics["total_practice_sessions"],
        },
        "recent_games": analytics["recent_games"],
        "recent_practice": analytics["recent_practice"],
    }


@router.get("/api/mobile/profile")
async def get_mobile_profile(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    return _mobile_profile_payload(user)


@router.patch("/api/mobile/profile")
async def update_mobile_profile(
    request: MobileProfileUpdateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    try:
        updated_user = account_store.update_mobile_profile(
            int(user["id"]),
            display_name=request.display_name,
            bio=request.bio,
            avatar_url=request.avatar_url,
        )
    except AccountError as exc:
        raise _account_error_response(exc) from exc
    _sync_supabase_mobile_profile(updated_user)
    return _mobile_profile_payload(updated_user)


@router.get("/api/mobile/users/{target_user_id}/profile")
async def get_mobile_public_profile(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    viewer = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    return _mobile_profile_payload(target, int(viewer["id"]))


@router.get("/api/mobile/users/{target_user_id}/posts")
async def get_mobile_public_profile_posts(
    target_user_id: int,
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    viewer = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    supabase_posts = _get_profile_posts_from_supabase(target_user_id, limit, offset)
    if supabase_posts is None:
        posts, total = db.get_community_posts_for_user(
            target_user_id,
            viewer_user_id=int(viewer["id"]),
            limit=limit,
            offset=offset,
        )
    else:
        posts, total = supabase_posts
    return {"posts": posts, "total": total, "limit": limit, "offset": offset}


@router.get("/api/mobile/users/{target_user_id}/profile-page")
async def get_mobile_public_profile_page(
    target_user_id: int,
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    viewer = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    supabase_posts = _get_profile_posts_from_supabase(target_user_id, limit, offset)
    if supabase_posts is None:
        posts, total = db.get_community_posts_for_user(
            target_user_id,
            viewer_user_id=int(viewer["id"]),
            limit=limit,
            offset=offset,
        )
    else:
        posts, total = supabase_posts
    return {
        "profile": _mobile_profile_payload(target, int(viewer["id"])),
        "posts": posts,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/api/mobile/follows/{target_user_id}")
async def follow_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    try:
        return db.follow_user(int(user["id"]), target_user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FOLLOW", "message": str(exc)}) from exc


@router.delete("/api/mobile/follows/{target_user_id}")
async def unfollow_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    return db.unfollow_user(int(user["id"]), target_user_id)


@router.get("/api/mobile/feed/following")
async def get_mobile_following_feed(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    user = _current_user(authorization)
    posts, total = db.get_following_feed_posts(int(user["id"]), limit=limit, offset=offset)
    return {
        "posts": posts,
        "total": total,
        "limit": limit,
        "offset": offset,
        "hasMoreFollowing": offset + limit < total,
    }


@router.get("/api/mobile/feed/trending")
async def get_mobile_trending_feed(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    exclude_ids: str = "",
):
    user = _current_user(authorization)
    posts, total = db.get_trending_feed_posts(
        int(user["id"]),
        limit=limit,
        offset=offset,
        exclude_ids=_parse_exclude_ids(exclude_ids),
    )
    return {
        "posts": posts,
        "total": total,
        "limit": limit,
        "offset": offset,
        "hasMoreTrending": offset + limit < total,
    }


@router.get("/api/friends")
async def get_friends(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    return {"friends": account_store.list_friends(int(user["id"]))}


@router.post("/api/friends/invite-qr")
async def create_friend_invite(
    request: FriendInviteRequest | None = Body(default=None),
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    base_url = _resolve_invite_base_url(request.base_url if request else "")
    try:
        invite = account_store.create_friend_invite(int(user["id"]))
    except AccountError as exc:
        raise _account_error_response(exc) from exc
    query = f"token={quote(invite['token'])}"
    if base_url:
        query += f"&baseUrl={quote(base_url, safe='')}"
    qr_payload = f"cuevex://friend-invite?{query}"
    return {
        "qr_payload": qr_payload,
        "token": invite["token"],
        "expires_at": invite["expires_at"],
        "owner": invite["owner"],
    }


@router.post("/api/friends/accept-qr")
async def accept_friend_invite(
    request: Annotated[AcceptFriendInviteRequest, Body(...)],
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    token = _parse_invite_token(request.payload)
    try:
        result = account_store.accept_friend_invite(int(user["id"]), token)
    except AccountError as exc:
        raise _account_error_response(exc) from exc
    return result


@router.post("/api/friends/{friend_user_id}/start-game")
async def start_friend_game(friend_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    friend = account_store.get_public_user_by_id(friend_user_id)
    if friend is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Friend not found."})
    if not account_store.are_friends(int(user["id"]), friend_user_id):
        raise HTTPException(status_code=403, detail={"code": "FRIEND_REQUIRED", "message": "You can only start games with friends."})
    if start_friend_game_handler is None:
        raise HTTPException(status_code=503, detail={"code": "GAME_START_UNAVAILABLE", "message": "Game starter is unavailable."})
    return await start_friend_game_handler(str(user["username"]), str(friend["username"]))
