import os
from typing import Annotated, Any, Awaitable, Callable

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

import config
from auth.account_store import AccountError, AccountStore
from auth.account_store_factory import create_account_store
from database.database import Database
from storage.supabase_accounts import SupabaseAccountError
from storage.supabase_blocks import SupabaseBlockError, configured_supabase_block_repository
from storage.supabase_follows import SupabaseFollowError, configured_supabase_follow_repository
from storage.supabase_notifications import SupabaseNotificationError, configured_supabase_notification_repository
from storage.supabase_profiles import SupabaseProfileError, configured_supabase_profile_repository
from storage.supabase_posts import SupabasePostError, configured_supabase_post_repository
from services.mobile_push_notifications import MobilePushEvent, configured_mobile_push_notification_service


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


class NotificationSettingsUpdateRequest(BaseModel):
    push_enabled: bool | None = None
    post_likes_enabled: bool | None = None
    post_comments_enabled: bool | None = None
    comment_replies_enabled: bool | None = None
    comment_likes_enabled: bool | None = None
    new_followers_enabled: bool | None = None
    mutual_follows_enabled: bool | None = None
    account_security_enabled: bool | None = None
    login_changes_enabled: bool | None = None
    service_announcements_enabled: bool | None = None
    show_preview_enabled: bool | None = None
    type_only_enabled: bool | None = None
    quiet_hours_enabled: bool | None = None


class PushTokenRequest(BaseModel):
    expo_push_token: str
    device: str = ""
    platform: str = ""


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


def _notification_repo_or_error():
    repo = configured_supabase_notification_repository()
    if repo is None:
        raise HTTPException(
            status_code=500,
            detail={"code": "SUPABASE_NOT_CONFIGURED", "message": "Supabase notification settings are not configured."},
        )
    return repo


def _dispatch_mobile_push_notification(event: MobilePushEvent) -> None:
    service = configured_mobile_push_notification_service()
    if service is None:
        return
    try:
        service.dispatch(event)
    except Exception as exc:
        print(f"WARNING mobile push notification dispatch failed: {exc}")


def _actor_display_name(user: dict[str, Any]) -> str:
    return str(user.get("display_name") or user.get("username") or "使用者")


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
    is_deactivated = bool(profile_user.get("is_deactivated") or False)
    is_self = viewer_user_id == int(user["id"]) if viewer_user_id is not None else True
    block_state = _get_block_state(viewer_user_id, int(user["id"])) if viewer_user_id is not None else "none"
    is_block_limited = block_state != "none"
    can_view_private = is_self or (
        viewer_user_id is not None
        and is_private
        and _is_following_user(int(viewer_user_id), int(user["id"]))
    )
    is_public_blocked = (is_deactivated and not is_self) or (is_private and not can_view_private) or is_block_limited
    post_count = 0 if is_public_blocked else _count_profile_posts(int(user["id"]), viewer_user_id)
    payload = {
        "user": profile_user,
        "display_name": display_name,
        "bio": "" if is_block_limited else str(profile_user.get("bio") or ""),
        "avatar_url": str(profile_user.get("avatar_url") or ""),
        "player_level": "" if is_public_blocked else _player_level_for_user(profile_user, analytics),
        "followers_count": 0 if is_public_blocked else follow_counts["followers_count"],
        "following_count": 0 if is_public_blocked else follow_counts["following_count"],
        "post_count": post_count,
        "is_private": is_private,
        "is_deactivated": is_deactivated,
        "block_state": block_state,
        "is_blocked_by_me": block_state == "blocked_by_me",
        "has_blocked_me": block_state == "blocked_me",
    }
    if viewer_user_id is not None:
        payload["is_following"] = False if is_block_limited else _is_following_user(viewer_user_id, int(user["id"]))
        payload["is_self"] = is_self
    return payload


def _is_profile_content_blocked(target: dict[str, Any], viewer_user_id: int) -> bool:
    if viewer_user_id == int(target["id"]):
        return False
    profile_user = _merge_supabase_mobile_profile(target)
    if _has_block_between(viewer_user_id, int(target["id"])):
        return True
    if bool(profile_user.get("is_deactivated") or False):
        return True
    if bool(profile_user.get("is_private") or False):
        return not _is_following_user(viewer_user_id, int(target["id"]))
    return False


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


def _list_follow_refs(user_id: int, kind: str, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    repo = configured_supabase_follow_repository()
    if repo is None or not hasattr(repo, "list_follow_refs"):
        return db.list_follow_refs(user_id, kind, limit=limit, offset=offset)
    try:
        return repo.list_follow_refs(user_id, kind, limit=limit, offset=offset)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow list read failed; using local follow list: {exc}")
        return db.list_follow_refs(user_id, kind, limit=limit, offset=offset)


def _is_following_user(follower_user_id: int, following_user_id: int) -> bool:
    repo = configured_supabase_follow_repository()
    if repo is None or not hasattr(repo, "is_following"):
        return db.is_following_user(follower_user_id, following_user_id)
    try:
        return repo.is_following(follower_user_id, following_user_id)
    except SupabaseFollowError as exc:
        print(f"WARNING Supabase follow state read failed; using local follow state: {exc}")
        return db.is_following_user(follower_user_id, following_user_id)


def _get_block_state(viewer_user_id: int | None, target_user_id: int) -> str:
    if viewer_user_id is None or int(viewer_user_id) == int(target_user_id):
        return "none"
    repo = configured_supabase_block_repository()
    if repo is None:
        return db.get_block_state(int(viewer_user_id), int(target_user_id))
    try:
        return repo.block_state(int(viewer_user_id), int(target_user_id))
    except SupabaseBlockError as exc:
        print(f"WARNING Supabase block state read failed; using local block state: {exc}")
        return db.get_block_state(int(viewer_user_id), int(target_user_id))


def _has_block_between(user_a_id: int, user_b_id: int) -> bool:
    return _get_block_state(user_a_id, user_b_id) != "none"


def _list_block_related_user_ids(user_id: int) -> set[int]:
    repo = configured_supabase_block_repository()
    if repo is None:
        return set(db.list_block_related_user_ids(user_id))
    try:
        return repo.related_user_ids(user_id)
    except SupabaseBlockError as exc:
        print(f"WARNING Supabase block related read failed; using local block related users: {exc}")
        return set(db.list_block_related_user_ids(user_id))


def _list_blocked_user_refs(user_id: int) -> list[dict[str, Any]]:
    repo = configured_supabase_block_repository()
    if repo is None:
        return db.list_blocked_user_refs(user_id)
    try:
        return repo.list_blocked_user_refs(user_id)
    except SupabaseBlockError as exc:
        print(f"WARNING Supabase block list read failed; using local block list: {exc}")
        return db.list_blocked_user_refs(user_id)


def _remove_follow_between(user_a_id: int, user_b_id: int) -> None:
    follow_repo = configured_supabase_follow_repository()
    if follow_repo is not None:
        try:
            follow_repo.set_follow(user_a_id, user_b_id, False)
            follow_repo.set_follow(user_b_id, user_a_id, False)
        except SupabaseFollowError as exc:
            print(f"WARNING Supabase bilateral follow cleanup failed: {exc}")
    try:
        db.unfollow_user(user_a_id, user_b_id)
        db.unfollow_user(user_b_id, user_a_id)
    except Exception as exc:
        print(f"WARNING local bilateral follow cleanup failed: {exc}")


def _notify_follow_events(actor: dict[str, Any], target: dict[str, Any], was_mutual: bool) -> None:
    actor_id = int(actor["id"])
    target_id = int(target["id"])
    _dispatch_mobile_push_notification(MobilePushEvent(
        recipient_user_id=target_id,
        actor_user_id=actor_id,
        event_type="new_follower",
        source_type="user",
        source_id=actor_id,
        title="有人追蹤你",
        body=f"{_actor_display_name(actor)} 開始追蹤你",
        data={"user_id": actor_id},
    ))
    if was_mutual:
        _dispatch_mobile_push_notification(MobilePushEvent(
            recipient_user_id=target_id,
            actor_user_id=actor_id,
            event_type="mutual_follow",
            source_type="user",
            source_id=actor_id,
            title="你們已互相關注",
            body=f"你和 {_actor_display_name(actor)} 已互相關注",
            data={"user_id": actor_id},
        ))


def _are_mutual_follow_friends(user_a_id: int, user_b_id: int) -> bool:
    if _has_block_between(user_a_id, user_b_id):
        return False
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
        if _has_block_between(user_id, int(ref["user_id"])):
            continue
        friend = account_store.get_public_user_by_id(int(ref["user_id"]))
        if friend is None:
            continue
        friend["friendship_created_at"] = str(ref.get("friendship_created_at") or "")
        friends.append(friend)
    return friends


def _mobile_follow_user_payload(target_user_id: int, viewer_user_id: int, followed_at: str) -> dict[str, Any] | None:
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        return None
    if _has_block_between(viewer_user_id, target_user_id):
        return None
    profile = _mobile_profile_payload(target, viewer_user_id)
    return {
        "user": profile["user"],
        "display_name": profile["display_name"],
        "avatar_url": profile["avatar_url"],
        "player_level": profile["player_level"],
        "is_following": profile.get("is_following", False),
        "is_self": profile.get("is_self", False),
        "followed_at": followed_at,
    }


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
        if is_private is None:
            repo.upsert_profile(
                int(user["id"]),
                next_display_name,
                next_bio,
                next_avatar_url,
            )
        else:
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
    if post_repo is None:
        return None
    try:
        if hasattr(post_repo, "list_following_feed"):
            rpc_feed = post_repo.list_following_feed(
                viewer_user_id,
                limit=limit,
                offset=offset,
            )
            if rpc_feed is not None:
                return rpc_feed
        if follow_repo is None:
            return None
        following_user_ids = follow_repo.list_following_user_ids(viewer_user_id)
        blocked_user_ids = _list_block_related_user_ids(viewer_user_id)
        following_user_ids = [user_id for user_id in following_user_ids if user_id not in blocked_user_ids]
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


def _filter_visible_feed_posts(posts: list[dict[str, Any]], viewer_user_id: int) -> list[dict[str, Any]]:
    visible_posts: list[dict[str, Any]] = []
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
        if author_id == int(viewer_user_id):
            visible_posts.append(post)
            continue
        if _has_block_between(int(viewer_user_id), author_id):
            continue
        author = account_store.get_public_user_by_id(author_id)
        if author is None:
            visible_posts.append(post)
            continue
        merged_author = _merge_supabase_mobile_profile(author)
        if bool(merged_author.get("is_private") or merged_author.get("is_deactivated") or False):
            continue
        visible_posts.append(post)
    return visible_posts


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


@router.get("/api/mobile/notifications/settings")
async def get_mobile_notification_settings(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    repo = _notification_repo_or_error()
    try:
        return repo.get_settings(int(user["id"]))
    except SupabaseNotificationError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_NOTIFICATION_FAILED", "message": str(exc)}) from exc


@router.patch("/api/mobile/notifications/settings")
async def update_mobile_notification_settings(
    request: NotificationSettingsUpdateRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    repo = _notification_repo_or_error()
    updates = request.dict(exclude_none=True)
    try:
        return repo.update_settings(int(user["id"]), updates)
    except SupabaseNotificationError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_NOTIFICATION_FAILED", "message": str(exc)}) from exc


@router.post("/api/mobile/notifications/push-token")
async def register_mobile_push_token(
    request: PushTokenRequest,
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    repo = _notification_repo_or_error()
    try:
        token = repo.upsert_push_token(
            int(user["id"]),
            request.expo_push_token,
            device=request.device,
            platform=request.platform,
        )
        return {"status": "registered", "token": token}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PUSH_TOKEN", "message": str(exc)}) from exc
    except SupabaseNotificationError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_NOTIFICATION_FAILED", "message": str(exc)}) from exc


@router.post("/api/mobile/notifications/test-push")
async def send_mobile_test_push(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    service = configured_mobile_push_notification_service()
    if service is None:
        raise HTTPException(
            status_code=500,
            detail={"code": "SUPABASE_NOT_CONFIGURED", "message": "Supabase notification settings are not configured."},
        )
    result = service.dispatch(MobilePushEvent(
        recipient_user_id=int(user["id"]),
        actor_user_id=int(user["id"]),
        event_type="test_push",
        source_type="diagnostic",
        source_id=int(user["id"]),
        title="CueVex 測試通知",
        body="如果你看到這則通知，代表推播已可送達此裝置。",
        data={"diagnostic": True},
    ))
    return {"status": result.get("status"), "result": result}


@router.get("/api/mobile/notifications/events")
async def get_mobile_notification_events(
    authorization: Annotated[str | None, Header()] = None,
    limit: int = Query(20, ge=1, le=50),
    check_receipts: bool = Query(False),
):
    user = _current_user(authorization)
    repo = _notification_repo_or_error()
    try:
        events = repo.list_recent_events(int(user["id"]), limit)
    except SupabaseNotificationError as exc:
        raise HTTPException(status_code=500, detail={"code": "SUPABASE_NOTIFICATION_FAILED", "message": str(exc)}) from exc

    receipt_results: list[dict[str, Any]] = []
    if check_receipts:
        service = configured_mobile_push_notification_service()
        if service is not None:
            for event in events:
                if event.get("status") == "sent" and event.get("expo_ticket_ids"):
                    receipt_results.append(service.check_receipts_for_event(event))
            try:
                events = repo.list_recent_events(int(user["id"]), limit)
            except SupabaseNotificationError:
                pass
    return {"events": events, "receipt_results": receipt_results, "limit": limit}


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
    if _is_profile_content_blocked(target, int(viewer["id"])):
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
    is_profile_blocked = _is_profile_content_blocked(target, int(viewer["id"]))
    supabase_posts = None if is_profile_blocked else _get_profile_posts_from_supabase(target_user_id, limit, offset, int(viewer["id"]))
    if supabase_posts is None:
        if is_profile_blocked:
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


@router.get("/api/mobile/users/{target_user_id}/follows")
async def get_mobile_user_follows(
    target_user_id: int,
    authorization: Annotated[str | None, Header()] = None,
    kind: str = Query("followers", pattern="^(followers|following)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    viewer = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    if _is_profile_content_blocked(target, int(viewer["id"])):
        raise HTTPException(
            status_code=403,
            detail={"code": "PRIVATE_PROFILE", "message": "Follow lists are private for this account."},
        )
    refs, total = _list_follow_refs(target_user_id, kind, limit=limit, offset=offset)
    users: list[dict[str, Any]] = []
    for ref in refs:
        payload = _mobile_follow_user_payload(int(ref["user_id"]), int(viewer["id"]), str(ref.get("followed_at") or ""))
        if payload is not None:
            users.append(payload)
    return {
        "users": users,
        "total": total,
        "limit": limit,
        "offset": offset,
        "kind": kind,
    }


@router.get("/api/mobile/blocks")
async def get_mobile_blocks(authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    blocked_users: list[dict[str, Any]] = []
    for ref in _list_blocked_user_refs(int(user["id"])):
        blocked = account_store.get_public_user_by_id(int(ref["user_id"]))
        if blocked is None:
            continue
        profile_payload = _mobile_profile_payload(blocked, int(user["id"]))
        blocked_users.append(
            {
                "user": profile_payload["user"],
                "display_name": profile_payload["display_name"],
                "avatar_url": profile_payload["avatar_url"],
                "blocked_at": str(ref.get("blocked_at") or ""),
            }
        )
    return {"blocked_users": blocked_users, "total": len(blocked_users)}


@router.post("/api/mobile/blocks/{target_user_id}")
async def block_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    if int(user["id"]) == int(target_user_id):
        raise HTTPException(status_code=400, detail={"code": "INVALID_BLOCK", "message": "Cannot block yourself"})
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    repo = configured_supabase_block_repository()
    if repo is not None:
        try:
            result = repo.block_user(int(user["id"]), target_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_BLOCK", "message": str(exc)}) from exc
        except SupabaseBlockError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_BLOCK_FAILED", "message": str(exc)}) from exc
    else:
        try:
            result = db.block_user(int(user["id"]), target_user_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "INVALID_BLOCK", "message": str(exc)}) from exc
    _remove_follow_between(int(user["id"]), target_user_id)
    return result


@router.delete("/api/mobile/blocks/{target_user_id}")
async def unblock_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    repo = configured_supabase_block_repository()
    if repo is not None:
        try:
            return repo.unblock_user(int(user["id"]), target_user_id)
        except SupabaseBlockError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_BLOCK_FAILED", "message": str(exc)}) from exc
    return db.unblock_user(int(user["id"]), target_user_id)


@router.post("/api/mobile/follows/{target_user_id}")
async def follow_mobile_user(target_user_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    target = account_store.get_public_user_by_id(target_user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
    if int(user["id"]) == target_user_id:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FOLLOW", "message": "Cannot follow yourself"})
    if _has_block_between(int(user["id"]), target_user_id):
        raise HTTPException(status_code=403, detail={"code": "USER_BLOCKED", "message": "Blocked users cannot follow each other."})
    was_mutual = _is_following_user(target_user_id, int(user["id"]))
    repo = configured_supabase_follow_repository()
    if repo is not None:
        try:
            repo.set_follow(int(user["id"]), target_user_id, True)
        except SupabaseFollowError as exc:
            raise HTTPException(status_code=500, detail={"code": "SUPABASE_FOLLOW_FAILED", "message": str(exc)}) from exc
        _notify_follow_events(user, target, was_mutual)
        return {
            "follower_user_id": int(user["id"]),
            "following_user_id": target_user_id,
            "is_following": True,
        }
    try:
        result = db.follow_user(int(user["id"]), target_user_id)
        _sync_supabase_follow(int(user["id"]), target_user_id, True)
        _notify_follow_events(user, target, was_mutual)
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
    posts = _filter_visible_feed_posts(posts, int(user["id"]))
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
    posts = _filter_visible_feed_posts(posts, int(user["id"]))
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
