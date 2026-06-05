import os
from typing import Annotated, Any, Awaitable, Callable

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

import config
from auth.account_store import AccountError, AccountStore
from auth.account_store_factory import create_account_store
from database.database import Database
from storage.supabase_accounts import SupabaseAccountError
from storage.supabase_follows import SupabaseFollowError, configured_supabase_follow_repository
from storage.supabase_profiles import SupabaseProfileError, configured_supabase_profile_repository
from storage.supabase_posts import SupabasePostError, configured_supabase_post_repository


db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
account_store = create_account_store(db_path, int(getattr(config, "AUTH_SESSION_TTL_SECONDS", 7 * 24 * 60 * 60)))
db = Database(db_path)
router = APIRouter()

StartFriendGameHandler = Callable[[str, str], Awaitable[dict[str, Any]]]
start_friend_game_handler: StartFriendGameHandler | None = None


class MobileProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    is_private: bool | None = None


def set_start_friend_game_handler(handler: StartFriendGameHandler) -> None:
    global start_friend_game_handler
    start_friend_game_handler = handler


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization[7:].strip()


def _current_user(authorization: str | None) -> dict[str, Any]:
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


def _account_error_response(error: AccountError) -> HTTPException:
    status_code = 400
    if error.code == "USER_NOT_FOUND":
        status_code = 404
    if error.code in {"INVALID_FRIEND_INVITE", "FRIEND_INVITE_EXPIRED"}:
        status_code = 400
    if error.code == "FRIEND_REQUIRED":
        status_code = 403
    return HTTPException(status_code=status_code, detail={"code": error.code, "message": error.message})


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


def _is_official_mobile_user(user: dict[str, Any]) -> bool:
    username = str(user.get("username") or "").strip().casefold()
    display_name = str(user.get("display_name") or "").strip().casefold()
    return username == "cuevex" or display_name in {"cuevex", "cuevex 官方"}


def _player_level_for_user(user: dict[str, Any], analytics: dict[str, Any]) -> str:
    return "官方帳號" if _is_official_mobile_user(user) else _derive_player_level(analytics)


def _mobile_profile_payload(user: dict[str, Any], viewer_user_id: int | None = None) -> dict[str, Any]:
    profile_user = _merge_supabase_mobile_profile(user)
    analytics = db.get_player_analytics(str(user["username"]))
    display_name = str(profile_user.get("display_name") or "").strip() or str(user.get("username") or "").strip()
    follow_counts = _get_follow_counts(int(user["id"]))
    is_private = bool(profile_user.get("is_private") or False)
    is_self = viewer_user_id == int(user["id"]) if viewer_user_id is not None else True
    is_private_blocked = is_private and not is_self
    post_count = 0 if is_private_blocked else _count_profile_posts(int(user["id"]), viewer_user_id)
    payload = {
        "user": profile_user,
        "display_name": display_name,
        "bio": str(profile_user.get("bio") or ""),
        "avatar_url": str(profile_user.get("avatar_url") or ""),
        "player_level": _player_level_for_user(profile_user, analytics),
        "followers_count": follow_counts["followers_count"],
        "following_count": follow_counts["following_count"],
        "post_count": post_count,
        "is_private": is_private,
    }
    if viewer_user_id is not None:
        payload["is_following"] = _is_following_user(viewer_user_id, int(user["id"]))
        payload["is_self"] = is_self
    return payload


def _is_private_profile_blocked(target: dict[str, Any], viewer_user_id: int) -> bool:
    if viewer_user_id == int(target["id"]):
        return False
    profile_user = _merge_supabase_mobile_profile(target)
    return bool(profile_user.get("is_private") or False)


def _count_profile_posts(user_id: int, viewer_user_id: int | None = None) -> int:
    repo = configured_supabase_post_repository()
    if repo is None:
        return db.count_community_posts_for_user(user_id)
    try:
        _, total = repo.list_posts_for_user(user_id, limit=1, offset=0, viewer_user_id=viewer_user_id)
        return int(total)
    except SupabasePostError as exc:
        print(f"WARNING Supabase profile post count failed; using local post count: {exc}")
        return db.count_community_posts_for_user(user_id)


def _get_follow_counts(user_id: int) -> dict[str, int]:
    repo = configured_supabase_follow_repository()
    if repo is None:
        return db.get_follow_counts(user_id)
    try:
        return repo.follow_counts(user_id)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow count read failed; using local follow counts: {exc}")
        return db.get_follow_counts(user_id)


def _is_following_user(follower_user_id: int, following_user_id: int) -> bool:
    repo = configured_supabase_follow_repository()
    if repo is None:
        return db.is_following_user(follower_user_id, following_user_id)
    try:
        return repo.is_following(follower_user_id, following_user_id)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow state read failed; using local follow state: {exc}")
        return db.is_following_user(follower_user_id, following_user_id)


def _are_mutual_follow_friends(user_a_id: int, user_b_id: int) -> bool:
    return _is_following_user(user_a_id, user_b_id) and _is_following_user(user_b_id, user_a_id)


def _list_mutual_follow_friends(user_id: int) -> list[dict[str, Any]]:
    repo = configured_supabase_follow_repository()
    try:
        refs = repo.list_mutual_friend_refs(user_id) if repo is not None else db.list_mutual_follow_friend_refs(user_id)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase mutual friend read failed; using local mutual friends: {exc}")
        refs = db.list_mutual_follow_friend_refs(user_id)

    friends: list[dict[str, Any]] = []
    for ref in refs:
        friend = account_store.get_public_user_by_id(int(ref["user_id"]))
        if friend is None:
            continue
        friend["friendship_created_at"] = str(ref.get("friendship_created_at") or "")
        friends.append(friend)
    return friends


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
    merged["display_name"] = str(profile.get("display_name") or user.get("display_name") or "")
    merged["bio"] = str(profile.get("bio") or user.get("bio") or "")
    merged["avatar_url"] = str(profile.get("avatar_url") or user.get("avatar_url") or "")
    merged["is_private"] = bool(profile.get("is_private") or user.get("is_private") or False)
    return merged


def _sync_supabase_mobile_profile(user: dict[str, Any], is_private: bool | None = None, require_success: bool = False) -> None:
    repo = configured_supabase_profile_repository()
    if repo is None:
        return
    try:
        if is_private is not None:
            repo.update_privacy(int(user["id"]), is_private)
            return
        existing_profile = repo.get_profile(int(user["id"])) or {}
        next_display_name = str(user.get("display_name") or "") or str(existing_profile.get("display_name") or "")
        next_bio = str(user.get("bio") or "") or str(existing_profile.get("bio") or "")
        next_avatar_url = str(user.get("avatar_url") or "") or str(existing_profile.get("avatar_url") or "")
        repo.upsert_profile(
            int(user["id"]),
            next_display_name,
            next_bio,
            next_avatar_url,
            is_private,
        )
    except SupabaseProfileError as exc:
        if require_success:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_PROFILE_SYNC_FAILED", "message": str(exc)}) from exc
        print(f"WARNING Supabase profile sync failed; local profile remains active: {exc}")


def _sync_supabase_follow(follower_user_id: int, following_user_id: int, following: bool) -> None:
    repo = configured_supabase_follow_repository()
    if repo is None:
        return
    try:
        repo.set_follow(follower_user_id, following_user_id, following)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow sync failed; local follow state remains active: {exc}")


def _get_profile_posts_from_supabase(
    author_user_id: int,
    limit: int,
    offset: int,
    viewer_user_id: int | None,
) -> tuple[list[dict[str, Any]], int] | None:
    repo = configured_supabase_post_repository()
    if repo is None:
        return None
    try:
        posts, total = repo.list_posts_for_user(
            author_user_id,
            limit=limit,
            offset=offset,
            viewer_user_id=viewer_user_id,
        )
    except SupabasePostError as exc:
        print(f"WARNING Supabase profile posts read failed; using local posts: {exc}")
        return None
    if not posts and total == 0:
        return None
    return posts, total


def _get_following_feed_from_supabase(
    viewer_user_id: int,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int] | None:
    follow_repo = configured_supabase_follow_repository()
    post_repo = configured_supabase_post_repository()
    if follow_repo is None or post_repo is None:
        return None
    try:
        following_user_ids = follow_repo.list_following_user_ids(viewer_user_id)
        if not following_user_ids:
            return None
        posts, total = post_repo.list_posts_for_users(
            following_user_ids,
            limit=limit,
            offset=offset,
            viewer_user_id=viewer_user_id,
        )
    except (SupabaseFollowError, SupabasePostError) as exc:
        print(f"WARNING Supabase following feed read failed; using local following feed: {exc}")
        return None
    if not posts and total == 0:
        return None
    return posts, total


def _get_trending_feed_from_supabase(
    viewer_user_id: int,
    limit: int,
    offset: int,
    exclude_ids: list[int],
) -> tuple[list[dict[str, Any]], int] | None:
    post_repo = configured_supabase_post_repository()
    if post_repo is None:
        return None
    try:
        posts, total = post_repo.list_trending_posts(
            limit=limit,
            offset=offset,
            viewer_user_id=viewer_user_id,
            exclude_ids=exclude_ids,
        )
    except SupabasePostError as exc:
        print(f"WARNING Supabase trending feed read failed; using local trending feed: {exc}")
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
            is_private=request.is_private,
        )
    except AccountError as exc:
        raise _account_error_response(exc) from exc
    if request.is_private is not None:
        updated_user["is_private"] = request.is_private
    _sync_supabase_mobile_profile(updated_user, request.is_private, require_success=request.is_private is not None)
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
    if _is_private_profile_blocked(target, int(viewer["id"])):
        return {"posts": [], "total": 0, "limit": limit, "offset": offset}
    supabase_posts = _get_profile_posts_from_supabase(target_user_id, limit, offset, int(viewer["id"]))
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
    is_private_blocked = _is_private_profile_blocked(target, int(viewer["id"]))
    supabase_posts = None if is_private_blocked else _get_profile_posts_from_supabase(target_user_id, limit, offset, int(viewer["id"]))
    if supabase_posts is None:
        if is_private_blocked:
            posts, total = [], 0
        else:
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
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    if int(user["id"]) == target_user_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FOLLOW", "message": "Cannot follow yourself"})
    repo = configured_supabase_follow_repository()
    if repo is not None:
        try:
            repo.set_follow(int(user["id"]), target_user_id, True)
        except SupabaseFollowError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_FOLLOW_FAILED", "message": str(exc)}) from exc
        return {
            "follower_user_id": int(user["id"]),
            "following_user_id": target_user_id,
            "is_following": True,
        }
    try:
        result = db.follow_user(int(user["id"]), target_user_id)
        _sync_supabase_follow(int(user["id"]), target_user_id, True)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FOLLOW", "message": str(exc)}) from exc


@router.delete("/api/mobile/follows/{target_user_id}")
async def unfollow_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    repo = configured_supabase_follow_repository()
    if repo is not None:
        try:
            repo.set_follow(int(user["id"]), target_user_id, False)
        except SupabaseFollowError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_FOLLOW_FAILED", "message": str(exc)}) from exc
        return {
            "follower_user_id": int(user["id"]),
            "following_user_id": target_user_id,
            "is_following": False,
        }
    result = db.unfollow_user(int(user["id"]), target_user_id)
    _sync_supabase_follow(int(user["id"]), target_user_id, False)
    return result


@router.get("/api/mobile/feed/following")
async def get_mobile_following_feed(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    user = _current_user(authorization)
    supabase_feed = _get_following_feed_from_supabase(int(user["id"]), limit, offset)
    if supabase_feed is None:
        posts, total = db.get_following_feed_posts(int(user["id"]), limit=limit, offset=offset)
    else:
        posts, total = supabase_feed
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
    parsed_exclude_ids = _parse_exclude_ids(exclude_ids)
    supabase_feed = _get_trending_feed_from_supabase(int(user["id"]), limit, offset, parsed_exclude_ids)
    if supabase_feed is None:
        posts, total = db.get_trending_feed_posts(
            int(user["id"]),
            limit=limit,
            offset=offset,
            exclude_ids=parsed_exclude_ids,
        )
    else:
        posts, total = supabase_feed
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
    return {"friends": _list_mutual_follow_friends(int(user["id"]))}


@router.post("/api/friends/{friend_user_id}/start-game")
async def start_friend_game(friend_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    friend = account_store.get_public_user_by_id(friend_user_id)
    if friend is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "Friend not found."})
    if not _are_mutual_follow_friends(int(user["id"]), friend_user_id):
        raise HTTPException(status_code=403, detail={"code": "FRIEND_REQUIRED", "message": "You can only start games with friends."})
    if start_friend_game_handler is None:
        raise HTTPException(status_code=503, detail={"code": "GAME_START_UNAVAILABLE", "message": "Game starter is unavailable."})
    return await start_friend_game_handler(str(user["username"]), str(friend["username"]))
