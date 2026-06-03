import sys
import json
import base64
from pathlib import Path

import pytest
from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from auth.account_store import AccountError, AccountStore
from database.database import Database
from api import mobile_api
from api import community_api
from storage.supabase_storage import SupabaseStorageClient, SupabaseStorageConfig
from storage.supabase_storage import SupabaseStorageError


def make_store(tmp_path: Path) -> AccountStore:
    return AccountStore(str(tmp_path / "accounts.db"), session_ttl_seconds=60)


def create_users(store: AccountStore) -> tuple[dict, dict]:
    player_a = store.create_user("PlayerA", "Password123", "Question?", "Answer")
    player_b = store.create_user("PlayerB", "Password123", "Question?", "Answer")
    return player_a, player_b


def insert_feed_post(db: Database, user: dict, body: str) -> dict:
    return db.insert_community_post(
        {
            "user_id": int(user["id"]),
            "author_name": user["username"],
            "badge": "玩家",
            "title": body,
            "body": body,
            "image_urls": [],
            "image_transforms": [],
            "preview_type": "pool-table",
            "recording_id": None,
            "tone": "aqua",
        }
    )


def set_post_age(db: Database, post_id: int, days: int) -> None:
    with db.transaction() as conn:
        conn.execute(
            "UPDATE community_posts SET created_at = datetime('now', ?) WHERE id = ?",
            (f"-{days} days", post_id),
        )


def test_friend_invite_accepts_and_lists_both_users(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    player_a, player_b = create_users(store)

    invite = store.create_friend_invite(player_a["id"])
    result = store.accept_friend_invite(player_b["id"], invite["token"])

    assert result["friend"]["username"] == "PlayerA"
    assert result["already_friends"] is False
    assert store.are_friends(player_a["id"], player_b["id"])
    assert store.list_friends(player_a["id"])[0]["username"] == "PlayerB"
    assert store.list_friends(player_b["id"])[0]["username"] == "PlayerA"


def test_friend_invite_is_idempotent_for_existing_friendship(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    player_a, player_b = create_users(store)

    invite = store.create_friend_invite(player_a["id"])
    store.accept_friend_invite(player_b["id"], invite["token"])
    second = store.accept_friend_invite(player_b["id"], invite["token"])

    assert second["already_friends"] is True
    assert len(store.list_friends(player_a["id"])) == 1


def test_friend_invite_rejects_invalid_expired_and_self_scan(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    player_a, player_b = create_users(store)

    with pytest.raises(AccountError) as invalid:
        store.accept_friend_invite(player_b["id"], "not-a-real-token")
    assert invalid.value.code == "INVALID_FRIEND_INVITE"

    expired = store.create_friend_invite(player_a["id"], ttl_seconds=-1)
    with pytest.raises(AccountError) as expired_error:
        store.accept_friend_invite(player_b["id"], expired["token"])
    assert expired_error.value.code == "FRIEND_INVITE_EXPIRED"

    own_invite = store.create_friend_invite(player_a["id"])
    with pytest.raises(AccountError) as self_scan:
        store.accept_friend_invite(player_a["id"], own_invite["token"])
    assert self_scan.value.code == "CANNOT_FRIEND_SELF"


@pytest.mark.anyio
async def test_remote_invite_uses_public_https_base_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    mobile_api.db = Database(db_path)
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    monkeypatch.setattr(mobile_api.config, "MOBILE_PUBLIC_BASE_URL", "https://cuevex.example.com")
    monkeypatch.setattr(mobile_api.config, "MOBILE_REQUIRE_HTTPS_QR", True)

    result = await mobile_api.create_friend_invite(
        None,
        f"Bearer {session_a['token']}",
    )
    assert "baseUrl=https%3A%2F%2Fcuevex.example.com" in result["qr_payload"]


@pytest.mark.anyio
async def test_remote_invite_rejects_non_https_when_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    mobile_api.db = Database(db_path)
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    monkeypatch.setattr(mobile_api.config, "MOBILE_PUBLIC_BASE_URL", "")
    monkeypatch.setattr(mobile_api.config, "MOBILE_REQUIRE_HTTPS_QR", True)

    with pytest.raises(HTTPException) as exc:
        await mobile_api.create_friend_invite(
            mobile_api.FriendInviteRequest(base_url="http://192.168.1.23:8001"),
            f"Bearer {session_a['token']}",
        )
    assert exc.value.detail["code"] == "HTTPS_BASE_URL_REQUIRED"


@pytest.mark.anyio
async def test_mobile_api_dashboard_friend_qr_and_start_game(tmp_path: Path) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    mobile_api.db = Database(db_path)
    player_a, player_b = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    session_b = store.create_session(player_b["id"], player_b)
    started_games: list[tuple[str, str]] = []

    async def start_game(player1: str, player2: str) -> dict:
        started_games.append((player1, player2))
        return {"status": "game_started", "player1": player1, "player2": player2}

    mobile_api.set_start_friend_game_handler(start_game)

    auth_a = f"Bearer {session_a['token']}"
    auth_b = f"Bearer {session_b['token']}"

    dashboard = await mobile_api.get_mobile_dashboard(auth_a)
    assert dashboard["user"]["username"] == "PlayerA"

    profile = await mobile_api.get_mobile_profile(auth_a)
    assert profile["display_name"] == "PlayerA"
    assert profile["bio"] == ""
    assert profile["avatar_url"] == ""
    assert profile["followers_count"] == 0
    assert profile["following_count"] == 0
    assert profile["post_count"] == 0

    updated_profile = await mobile_api.update_mobile_profile(
        mobile_api.MobileProfileUpdateRequest(
            display_name="Lucian039",
            bio="九號球練習中",
            avatar_url="/api/community/uploads/avatar.jpg",
        ),
        auth_a,
    )
    assert updated_profile["display_name"] == "Lucian039"
    assert updated_profile["bio"] == "九號球練習中"
    assert updated_profile["avatar_url"] == "/api/community/uploads/avatar.jpg"

    mobile_api.db.insert_community_post(
        {
            "user_id": player_a["id"],
            "author_name": "PlayerA",
            "badge": "新手玩家 I",
            "title": "練習紀錄",
            "body": "今天完成一組九號球練習。",
            "preview_type": "pool-table",
        }
    )
    profile_with_post = await mobile_api.get_mobile_profile(auth_a)
    assert profile_with_post["post_count"] == 1

    invite = await mobile_api.create_friend_invite(
        mobile_api.FriendInviteRequest(base_url="http://192.168.1.23:8001"),
        auth_a,
    )
    assert invite["qr_payload"].startswith("cuevex://friend-invite?")

    accepted = await mobile_api.accept_friend_invite(
        mobile_api.AcceptFriendInviteRequest(payload=invite["qr_payload"]),
        auth_b,
    )
    assert accepted["friend"]["username"] == "PlayerA"

    friends = await mobile_api.get_friends(auth_a)
    assert friends["friends"][0]["username"] == "PlayerB"

    game = await mobile_api.start_friend_game(player_b["id"], auth_a)
    assert game["status"] == "game_started"
    assert started_games == [("PlayerA", "PlayerB")]


@pytest.mark.anyio
async def test_mobile_profile_reads_supabase_profile_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    mobile_api.db = Database(db_path)
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"

    class FakeProfileRepository:
        def get_profile(self, user_id: int) -> dict:
            return {
                "user_id": user_id,
                "display_name": "Supabase Name",
                "bio": "Supabase bio",
                "avatar_url": "https://example.com/avatar.jpg",
            }

    monkeypatch.setattr(mobile_api, "configured_supabase_profile_repository", lambda: FakeProfileRepository())

    profile = await mobile_api.get_mobile_profile(auth_a)

    assert profile["display_name"] == "Supabase Name"
    assert profile["bio"] == "Supabase bio"
    assert profile["avatar_url"] == "https://example.com/avatar.jpg"
    assert profile["user"]["display_name"] == "Supabase Name"


@pytest.mark.anyio
async def test_mobile_profile_update_syncs_supabase_without_blocking_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    mobile_api.db = Database(db_path)
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"
    upserts: list[dict] = []

    class FakeProfileRepository:
        def get_profile(self, user_id: int) -> None:
            return None

        def upsert_profile(self, user_id: int, display_name: str, bio: str, avatar_url: str) -> dict:
            upserts.append({"user_id": user_id, "display_name": display_name, "bio": bio, "avatar_url": avatar_url})
            return upserts[-1]

    monkeypatch.setattr(mobile_api, "configured_supabase_profile_repository", lambda: FakeProfileRepository())

    profile = await mobile_api.update_mobile_profile(
        mobile_api.MobileProfileUpdateRequest(
            display_name="Lucian039",
            bio="九號球練習中",
            avatar_url="https://example.com/avatar.jpg",
        ),
        auth_a,
    )

    assert profile["display_name"] == "Lucian039"
    assert upserts == [
        {
            "user_id": player_a["id"],
            "display_name": "Lucian039",
            "bio": "九號球練習中",
            "avatar_url": "https://example.com/avatar.jpg",
        }
    ]


@pytest.mark.anyio
async def test_mobile_follow_api_updates_profile_counts(tmp_path: Path) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    mobile_api.db = Database(db_path)
    player_a, player_b = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"

    followed = await mobile_api.follow_mobile_user(player_b["id"], auth_a)
    assert followed["is_following"] is True

    profile_a = await mobile_api.get_mobile_profile(auth_a)
    assert profile_a["following_count"] == 1
    assert profile_a["followers_count"] == 0

    session_b = store.create_session(player_b["id"], player_b)
    profile_b = await mobile_api.get_mobile_profile(f"Bearer {session_b['token']}")
    assert profile_b["followers_count"] == 1
    assert profile_b["following_count"] == 0

    unfollowed = await mobile_api.unfollow_mobile_user(player_b["id"], auth_a)
    assert unfollowed["is_following"] is False
    profile_a_after = await mobile_api.get_mobile_profile(auth_a)
    assert profile_a_after["following_count"] == 0


@pytest.mark.anyio
async def test_mobile_public_profile_posts_and_follow_state(tmp_path: Path) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    db = Database(db_path)
    mobile_api.db = db
    player_a, player_b = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"
    post_b = insert_feed_post(db, player_b, "對方主頁貼文")

    profile_before = await mobile_api.get_mobile_public_profile(player_b["id"], auth_a)
    assert profile_before["is_self"] is False
    assert profile_before["is_following"] is False

    await mobile_api.follow_mobile_user(player_b["id"], auth_a)
    profile_after = await mobile_api.get_mobile_public_profile(player_b["id"], auth_a)
    assert profile_after["is_following"] is True
    assert profile_after["followers_count"] == 1

    db.toggle_community_like(post_b["id"], int(player_a["id"]))
    posts = await mobile_api.get_mobile_public_profile_posts(player_b["id"], auth_a, limit=10, offset=0)
    assert posts["total"] == 1
    assert posts["posts"][0]["id"] == post_b["id"]
    assert posts["posts"][0]["liked_by_me"] is True

    page = await mobile_api.get_mobile_public_profile_page(player_b["id"], auth_a, limit=10, offset=0)
    assert page["profile"]["user"]["id"] == player_b["id"]
    assert page["profile"]["is_self"] is False
    assert page["profile"]["is_following"] is True
    assert page["total"] == 1
    assert page["limit"] == 10
    assert page["offset"] == 0
    assert page["posts"][0]["id"] == post_b["id"]

    self_page = await mobile_api.get_mobile_public_profile_page(player_a["id"], auth_a, limit=10, offset=0)
    assert self_page["profile"]["is_self"] is True

    with pytest.raises(HTTPException) as missing_user:
        await mobile_api.get_mobile_public_profile_page(9999, auth_a, limit=10, offset=0)
    assert missing_user.value.status_code == 404


@pytest.mark.anyio
async def test_mobile_public_profile_posts_prefers_supabase_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    mobile_api.db = Database(db_path)
    player_a, player_b = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"
    insert_feed_post(mobile_api.db, player_b, "local post")

    class FakePostRepository:
        def list_posts_for_user(self, user_id: int, limit: int, offset: int) -> tuple[list[dict], int]:
            return (
                [
                    {
                        "id": 999,
                        "user_id": user_id,
                        "author_name": "PlayerB",
                        "author_avatar_url": "",
                        "badge": "玩家",
                        "title": "",
                        "body": "supabase post",
                        "image_urls": [],
                        "image_transforms": [],
                        "preview_type": "pool-table",
                        "recording_id": None,
                        "tone": "aqua",
                        "created_at": "2026-06-03T00:00:00Z",
                        "updated_at": "2026-06-03T00:00:00Z",
                        "likes": 0,
                        "comments": 0,
                        "shares": 0,
                        "liked_by_me": False,
                        "bookmarked_by_me": False,
                    }
                ],
                1,
            )

    monkeypatch.setattr(mobile_api, "configured_supabase_post_repository", lambda: FakePostRepository())

    posts = await mobile_api.get_mobile_public_profile_posts(player_b["id"], auth_a, limit=10, offset=0)
    page = await mobile_api.get_mobile_public_profile_page(player_b["id"], auth_a, limit=10, offset=0)

    assert posts["posts"][0]["body"] == "supabase post"
    assert posts["posts"][0]["id"] == 999
    assert page["posts"][0]["body"] == "supabase post"
    assert page["total"] == 1


@pytest.mark.anyio
async def test_mobile_feed_following_and_trending_sorting(tmp_path: Path) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    mobile_api.account_store = store
    db = Database(db_path)
    mobile_api.db = db
    player_a, player_b = create_users(store)
    player_c = store.create_user("PlayerC", "Password123", "Question?", "Answer")
    player_d = store.create_user("PlayerD", "Password123", "Question?", "Answer")
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"

    await mobile_api.follow_mobile_user(player_b["id"], auth_a)
    hot_following = insert_feed_post(db, player_b, "追蹤熱門")
    fresh_following = insert_feed_post(db, player_b, "追蹤最新")
    old_following = insert_feed_post(db, player_b, "追蹤過舊")
    global_hot = insert_feed_post(db, player_c, "全站熱門")
    excluded_global = insert_feed_post(db, player_d, "排除貼文")
    set_post_age(db, old_following["id"], 8)

    db.toggle_community_like(hot_following["id"], int(player_a["id"]))
    db.insert_community_comment(hot_following["id"], int(player_a["id"]), player_a["username"], "好球")
    db.insert_community_comment(global_hot["id"], int(player_a["id"]), player_a["username"], "留言一")
    db.insert_community_comment(global_hot["id"], int(player_b["id"]), player_b["username"], "留言二")
    db.toggle_community_like(excluded_global["id"], int(player_a["id"]))
    db.toggle_community_like(excluded_global["id"], int(player_b["id"]))
    db.toggle_community_like(excluded_global["id"], int(player_c["id"]))

    following_feed = await mobile_api.get_mobile_following_feed(auth_a, limit=10, offset=0)
    following_ids = [post["id"] for post in following_feed["posts"]]
    assert following_ids == [hot_following["id"], fresh_following["id"]]
    assert following_feed["posts"][0]["feed_score"] == 3
    assert following_feed["hasMoreFollowing"] is False

    trending_feed = await mobile_api.get_mobile_trending_feed(
        auth_a,
        limit=10,
        offset=0,
        exclude_ids=str(excluded_global["id"]),
    )
    trending_ids = [post["id"] for post in trending_feed["posts"]]
    assert excluded_global["id"] not in trending_ids
    assert trending_ids[0] == global_hot["id"]
    assert old_following["id"] not in trending_ids
    assert trending_feed["posts"][0]["feed_score"] == 4


@pytest.mark.anyio
async def test_community_post_images_upload_and_following_feed(tmp_path: Path) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    community_api.account_store = store
    community_api.db = Database(db_path)
    community_api.UPLOAD_DIR = str(tmp_path / "uploads")
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"

    feed = await community_api.get_community_posts(auth_a, tab="following", sort="latest", limit=10, offset=0)
    assert feed["posts"] == []

    upload = await community_api.upload_community_images(
        community_api.CommunityUploadRequest(
            images=[
                community_api.CommunityUploadImage(
                    filename="shot.jpg",
                    mime_type="image/jpeg",
                    data="aW1hZ2UtYnl0ZXM=",
                )
            ]
        ),
        auth_a,
    )
    assert upload["image_urls"][0].startswith("/api/community/uploads/")

    post = await community_api.create_community_post(
        community_api.CommunityPostRequest(body="新開的球館歡迎大家來打球", image_urls=upload["image_urls"]),
        auth_a,
    )
    post_body = json.loads(post.body)
    assert post_body["title"] == ""
    assert post_body["image_urls"] == upload["image_urls"]

    feed_after_post = await community_api.get_community_posts(auth_a, tab="following", sort="latest", limit=10, offset=0)
    assert feed_after_post["total"] == 1
    assert feed_after_post["posts"][0]["image_urls"] == upload["image_urls"]

    deleted = await community_api.delete_community_post(feed_after_post["posts"][0]["id"], auth_a)
    assert deleted["status"] == "deleted"
    feed_after_delete = await community_api.get_community_posts(auth_a, tab="following", sort="latest", limit=10, offset=0)
    assert feed_after_delete["total"] == 0


def test_community_upload_size_limit_message() -> None:
    community_api.MAX_UPLOAD_BYTES = 4
    encoded = base64.b64encode(b"12345").decode("ascii")
    with pytest.raises(HTTPException) as exc:
        community_api._decode_image_data(encoded)
    assert exc.value.detail["code"] == "IMAGE_TOO_LARGE"
    assert "15MB" in exc.value.detail["message"]


@pytest.mark.anyio
async def test_create_community_post_syncs_supabase_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    community_api.account_store = store
    community_api.db = Database(db_path)
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"
    synced_posts: list[dict] = []

    class FakePostRepository:
        def upsert_post(self, post: dict) -> dict:
            synced_posts.append(post)
            return post

    monkeypatch.setattr(community_api, "configured_supabase_post_repository", lambda: FakePostRepository())

    response = await community_api.create_community_post(
        community_api.CommunityPostRequest(
            body="練球紀錄",
            image_urls=["https://example.com/shot.jpg"],
            image_transforms=[{"x": 0, "y": 1, "scale": 1, "width": 100, "height": 120, "frame_width": 300}],
        ),
        auth_a,
    )
    post_body = json.loads(response.body)

    assert post_body["title"] == ""
    assert len(synced_posts) == 1
    assert synced_posts[0]["id"] == post_body["id"]
    assert synced_posts[0]["title"] == ""
    assert synced_posts[0]["body"] == "練球紀錄"
    assert synced_posts[0]["image_urls"] == ["https://example.com/shot.jpg"]

@pytest.mark.anyio
async def test_delete_community_post_syncs_supabase_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    community_api.account_store = store
    community_api.db = Database(db_path)
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"
    deleted_posts: list[int] = []

    class FakePostRepository:
        def upsert_post(self, post: dict) -> dict:
            return post

        def delete_post(self, post_id: int) -> None:
            deleted_posts.append(post_id)

    monkeypatch.setattr(community_api, "configured_supabase_post_repository", lambda: FakePostRepository())

    response = await community_api.create_community_post(
        community_api.CommunityPostRequest(body="delete sync test"),
        auth_a,
    )
    post_id = json.loads(response.body)["id"]
    deleted = await community_api.delete_community_post(post_id, auth_a)

    assert deleted == {"status": "deleted", "post_id": post_id}
    assert deleted_posts == [post_id]


def test_supabase_storage_uses_apikey_only_for_secret_key() -> None:
    client = SupabaseStorageClient(
        SupabaseStorageConfig(
            url="https://cuevex.supabase.co",
            service_role_key="sb_secret_test_key",
            bucket="community-uploads",
        )
    )

    headers = client._auth_headers()

    assert headers["apikey"] == "sb_secret_test_key"
    assert "Authorization" not in headers


@pytest.mark.anyio
async def test_create_community_comment_syncs_supabase_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    community_api.account_store = store
    community_api.db = Database(db_path)
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"
    synced_comments: list[dict] = []

    class FakeCommentRepository:
        def upsert_comment(self, comment: dict) -> dict:
            synced_comments.append(comment)
            return comment

    monkeypatch.setattr(community_api, "configured_supabase_comment_repository", lambda: FakeCommentRepository())

    post_response = await community_api.create_community_post(
        community_api.CommunityPostRequest(body="comment sync post"),
        auth_a,
    )
    post_id = json.loads(post_response.body)["id"]
    comment_response = await community_api.create_community_comment(
        post_id,
        community_api.CommunityCommentRequest(body="first comment"),
        auth_a,
    )
    body = json.loads(comment_response.body)

    assert body["comment"]["body"] == "first comment"
    assert len(synced_comments) == 1
    assert synced_comments[0]["id"] == body["comment"]["id"]
    assert synced_comments[0]["post_id"] == post_id
    assert synced_comments[0]["user_id"] == player_a["id"]
    assert synced_comments[0]["body"] == "first comment"


@pytest.mark.anyio
async def test_get_community_comments_prefers_supabase_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    community_api.account_store = store
    db = Database(db_path)
    community_api.db = db
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"
    post = insert_feed_post(db, player_a, "comment read post")
    db.insert_community_comment(post["id"], player_a["id"], player_a["username"], "local comment")

    class FakeCommentRepository:
        def list_comments_for_post(self, post_id: int) -> list[dict]:
            return [
                {
                    "id": 999,
                    "post_id": post_id,
                    "user_id": player_a["id"],
                    "author_name": player_a["username"],
                    "author_avatar_url": "",
                    "author_player_level": "",
                    "body": "supabase comment",
                    "created_at": "2026-06-03T00:00:00Z",
                    "likes": 0,
                    "liked_by_me": False,
                }
            ]

    monkeypatch.setattr(community_api, "configured_supabase_comment_repository", lambda: FakeCommentRepository())

    response = await community_api.get_community_comments(post["id"], auth_a)

    assert response["total"] == 1
    assert response["comments"][0]["id"] == 999
    assert response["comments"][0]["body"] == "supabase comment"


@pytest.mark.anyio
async def test_community_upload_uses_supabase_storage_when_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    community_api.account_store = store
    community_api.db = Database(db_path)
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"
    uploads: list[tuple[str, bytes, str]] = []

    class FakeSupabaseStorageClient:
        def upload_public_object(self, object_path: str, content: bytes, mime_type: str) -> str:
            uploads.append((object_path, content, mime_type))
            return f"https://cuevex.supabase.co/storage/v1/object/public/community-uploads/{object_path}"

    monkeypatch.setattr(community_api, "configured_supabase_storage_client", lambda: FakeSupabaseStorageClient())

    upload = await community_api.upload_community_images(
        community_api.CommunityUploadRequest(
            purpose="avatar",
            images=[
                community_api.CommunityUploadImage(
                    filename="avatar.jpg",
                    mime_type="image/jpeg",
                    data=base64.b64encode(b"avatar-bytes").decode("ascii"),
                )
            ],
        ),
        auth_a,
    )

    assert upload["image_urls"][0].startswith("https://cuevex.supabase.co/storage/v1/object/public/community-uploads/")
    assert uploads[0][0].startswith(f"users/{player_a['id']}/avatars/")
    assert uploads[0][0].endswith(".jpg")
    assert uploads[0][1] == b"avatar-bytes"
    assert uploads[0][2] == "image/jpeg"


@pytest.mark.anyio
async def test_community_upload_falls_back_to_local_when_supabase_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = str(tmp_path / "accounts.db")
    store = AccountStore(db_path, session_ttl_seconds=60)
    community_api.account_store = store
    community_api.db = Database(db_path)
    community_api.UPLOAD_DIR = str(tmp_path / "uploads")
    player_a, _ = create_users(store)
    session_a = store.create_session(player_a["id"], player_a)
    auth_a = f"Bearer {session_a['token']}"

    class FailingSupabaseStorageClient:
        def upload_public_object(self, object_path: str, content: bytes, mime_type: str) -> str:
            raise SupabaseStorageError("test failure")

    monkeypatch.setattr(community_api, "configured_supabase_storage_client", lambda: FailingSupabaseStorageClient())

    upload = await community_api.upload_community_images(
        community_api.CommunityUploadRequest(
            purpose="avatar",
            images=[
                community_api.CommunityUploadImage(
                    filename="avatar.jpg",
                    mime_type="image/jpeg",
                    data=base64.b64encode(b"avatar-bytes").decode("ascii"),
                )
            ],
        ),
        auth_a,
    )

    assert upload["image_urls"][0].startswith("/api/community/uploads/")
    saved_name = upload["image_urls"][0].rsplit("/", 1)[-1]
    assert (tmp_path / "uploads" / saved_name).read_bytes() == b"avatar-bytes"
