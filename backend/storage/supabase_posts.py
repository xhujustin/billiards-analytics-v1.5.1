import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error, parse, request

from storage.supabase_bookmarks import SupabaseBookmarkError, configured_supabase_bookmark_repository
from storage.supabase_comments import SupabaseCommentError, configured_supabase_comment_repository
from storage.supabase_profiles import SupabaseProfileError, configured_supabase_profile_repository
from storage.supabase_reactions import SupabaseReactionError, configured_supabase_reaction_repository


class SupabasePostError(RuntimeError):
    """Raised when Supabase community post sync cannot complete."""


@dataclass(frozen=True)
class SupabasePostConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabasePostConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseCommunityPostRepository:
    def __init__(self, config: SupabasePostConfig):
        self.config = config

    def create_post(self, post: dict[str, Any], viewer_user_id: int | None = None) -> dict[str, Any]:
        now = _utc_now_iso()
        payload = {
            "id": int(post.get("id") or _new_bigint_id()),
            "user_id": int(post["user_id"]) if post.get("user_id") is not None else None,
            "author_name": str(post.get("author_name") or ""),
            "badge": str(post.get("badge") or ""),
            "title": str(post.get("title") or ""),
            "body": str(post.get("body") or ""),
            "preview_type": str(post.get("preview_type") or "pool-table"),
            "recording_id": post.get("recording_id"),
            "tone": str(post.get("tone") or ""),
            "image_urls": post.get("image_urls") if isinstance(post.get("image_urls"), list) else [],
            "image_transforms": post.get("image_transforms") if isinstance(post.get("image_transforms"), list) else [],
            "created_at": str(post.get("created_at") or now),
            "updated_at": str(post.get("updated_at") or now),
        }
        row = self._insert_post_row(payload)
        return self._posts_from_rows([row], viewer_user_id)[0]

    def upsert_post(self, post: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self.config.url}/rest/v1/community_posts?on_conflict=id"
        payload = {
            "id": int(post["id"]),
            "user_id": int(post["user_id"]) if post.get("user_id") is not None else None,
            "author_name": str(post.get("author_name") or ""),
            "badge": str(post.get("badge") or ""),
            "title": str(post.get("title") or ""),
            "body": str(post.get("body") or ""),
            "preview_type": str(post.get("preview_type") or "pool-table"),
            "recording_id": post.get("recording_id"),
            "tone": str(post.get("tone") or ""),
            "image_urls": post.get("image_urls") if isinstance(post.get("image_urls"), list) else [],
            "image_transforms": post.get("image_transforms") if isinstance(post.get("image_transforms"), list) else [],
            "created_at": post["created_at"],
            "updated_at": post["updated_at"],
        }
        data = self._request_json(
            endpoint,
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
        )
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise SupabasePostError("Supabase post upsert returned no row.")
        return data[0]

    def get_post(self, post_id: int, viewer_user_id: int | None = None) -> dict[str, Any] | None:
        rpc_posts = self.hydrated_posts([post_id], viewer_user_id)
        if rpc_posts:
            return rpc_posts[0]
        query = parse.urlencode(
            {
                "id": f"eq.{int(post_id)}",
                "select": "id,user_id,author_name,badge,title,body,preview_type,recording_id,tone,image_urls,image_transforms,created_at,updated_at",
                "limit": "1",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_posts?{query}"
        rows = self._request_json(endpoint, method="GET")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        posts = self._posts_from_rows([rows[0]], viewer_user_id)
        return posts[0] if posts else None

    def hydrated_posts(self, post_ids: list[int], viewer_user_id: int | None = None) -> list[dict[str, Any]]:
        ids = [int(post_id) for post_id in post_ids if int(post_id) > 0]
        if not ids:
            return []
        data = self._rpc_json(
            "mobile_hydrated_posts",
            {
                "viewer_user_id": int(viewer_user_id or 0),
                "post_ids": ids,
            },
            allow_missing=True,
        )
        if not isinstance(data, list):
            return []
        posts = [self._post_from_rpc_row(row) for row in data if isinstance(row, dict)]
        order = {post_id: index for index, post_id in enumerate(ids)}
        posts.sort(key=lambda post: order.get(int(post.get("id") or 0), len(order)))
        return posts

    def toggle_post_like(self, post_id: int, viewer_user_id: int) -> dict[str, Any] | None:
        data = self._rpc_json(
            "mobile_toggle_post_like",
            {
                "viewer_user_id": int(viewer_user_id),
                "post_id": int(post_id),
            },
            allow_missing=True,
        )
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if isinstance(row, dict):
                return self._post_from_rpc_row(row)
        return None

    def toggle_post_bookmark(self, post_id: int, viewer_user_id: int) -> dict[str, Any] | None:
        data = self._rpc_json(
            "mobile_toggle_post_bookmark",
            {
                "viewer_user_id": int(viewer_user_id),
                "post_id": int(post_id),
            },
            allow_missing=True,
        )
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if isinstance(row, dict):
                return self._post_from_rpc_row(row)
        return None

    def delete_post(self, post_id: int) -> None:
        query = parse.urlencode({"id": f"eq.{int(post_id)}"})
        endpoint = f"{self.config.url}/rest/v1/community_posts?{query}"
        self._request_json(endpoint, method="DELETE")

    def _insert_post_row(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self.config.url}/rest/v1/community_posts"
        data = self._request_json(
            endpoint,
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise SupabasePostError("Supabase post create returned no row.")
        return data[0]


    def list_posts_for_user(
        self,
        user_id: int,
        limit: int,
        offset: int,
        viewer_user_id: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rpc_result = self._list_user_posts_rpc(user_id, limit, offset, viewer_user_id)
        if rpc_result is not None:
            return rpc_result
        count_query = parse.urlencode({"user_id": f"eq.{int(user_id)}", "select": "id"})
        count_endpoint = f"{self.config.url}/rest/v1/community_posts?{count_query}"
        count_headers = {"Prefer": "count=exact"}
        total_data, total_count = self._request_json_with_count(count_endpoint, method="GET", extra_headers=count_headers)
        total = total_count if total_count is not None else len(total_data or [])

        query = parse.urlencode(
            {
                "user_id": f"eq.{int(user_id)}",
                "select": "id,user_id,author_name,badge,title,body,preview_type,recording_id,tone,image_urls,image_transforms,created_at,updated_at",
                "order": "created_at.desc,id.desc",
                "limit": str(limit),
                "offset": str(offset),
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_posts?{query}"
        rows = self._request_json(endpoint, method="GET")
        if not isinstance(rows, list):
            return [], int(total)
        post_rows = [row for row in rows if isinstance(row, dict)]
        post_ids = [int(row["id"]) for row in post_rows if row.get("id") is not None]
        reaction_summary = self._post_reaction_summary(post_ids, viewer_user_id)
        comment_counts = self._post_comment_counts(post_ids)
        bookmark_summary = self._post_bookmark_summary(post_ids, viewer_user_id)
        author_profiles = self._author_profiles(post_rows)
        posts = [
            self._post_from_row(
                row,
                author_profile=author_profiles.get(int(row["user_id"])) if row.get("user_id") is not None else None,
                likes=int(reaction_summary.get(int(row["id"]), {}).get("likes", 0)),
                comments=int(comment_counts.get(int(row["id"]), 0)),
                liked_by_me=bool(reaction_summary.get(int(row["id"]), {}).get("liked_by_me", False)),
                bookmarked_by_me=bool(bookmark_summary.get(int(row["id"]), False)),
            )
            for row in post_rows
            if row.get("id") is not None
        ]
        return posts, int(total)

    def list_posts_for_users(
        self,
        user_ids: list[int],
        limit: int,
        offset: int,
        viewer_user_id: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        if not ids:
            return [], 0
        id_filter = ",".join(str(user_id) for user_id in ids)
        base_filter = {"user_id": f"in.({id_filter})"}
        count_query = parse.urlencode({**base_filter, "select": "id"})
        count_endpoint = f"{self.config.url}/rest/v1/community_posts?{count_query}"
        total_data, total_count = self._request_json_with_count(
            count_endpoint,
            method="GET",
            extra_headers={"Prefer": "count=exact"},
        )
        total = total_count if total_count is not None else len(total_data or [])

        query = parse.urlencode(
            {
                **base_filter,
                "select": "id,user_id,author_name,badge,title,body,preview_type,recording_id,tone,image_urls,image_transforms,created_at,updated_at",
                "order": "created_at.desc,id.desc",
                "limit": str(limit),
                "offset": str(offset),
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_posts?{query}"
        rows = self._request_json(endpoint, method="GET")
        if not isinstance(rows, list):
            return [], int(total)
        return self._posts_from_rows(rows, viewer_user_id), int(total)

    def list_following_feed(
        self,
        viewer_user_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int] | None:
        return self._list_following_feed_rpc(limit, offset, viewer_user_id)

    def list_bookmarked_posts(
        self,
        viewer_user_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int] | None:
        data = self._rpc_json(
            "mobile_bookmarked_posts",
            {
                "viewer_user_id": int(viewer_user_id),
                "page_limit": int(limit),
                "page_offset": int(offset),
            },
            allow_missing=True,
        )
        return self._posts_with_total_from_rpc_rows(data)

    def list_posts_by_ids(self, post_ids: list[int], viewer_user_id: int | None = None) -> list[dict[str, Any]]:
        ids = [int(post_id) for post_id in post_ids if int(post_id) > 0]
        if not ids:
            return []
        rpc_posts = self.hydrated_posts(ids, viewer_user_id)
        if rpc_posts:
            return rpc_posts
        id_filter = ",".join(str(post_id) for post_id in sorted(set(ids)))
        query = parse.urlencode(
            {
                "id": f"in.({id_filter})",
                "select": "id,user_id,author_name,badge,title,body,preview_type,recording_id,tone,image_urls,image_transforms,created_at,updated_at",
            }
        )
        rows = self._request_json(f"{self.config.url}/rest/v1/community_posts?{query}", method="GET")
        if not isinstance(rows, list):
            return []
        posts = self._posts_from_rows(rows, viewer_user_id)
        order = {post_id: index for index, post_id in enumerate(ids)}
        posts.sort(key=lambda post: order.get(int(post.get("id") or 0), len(order)))
        return posts

    def list_trending_posts(
        self,
        limit: int,
        offset: int,
        viewer_user_id: int | None = None,
        exclude_ids: list[int] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rpc_result = self._list_trending_feed_rpc(limit, offset, viewer_user_id, exclude_ids or [])
        if rpc_result is not None:
            return rpc_result
        excluded = sorted({int(post_id) for post_id in (exclude_ids or []) if int(post_id) > 0})
        cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat().replace("+00:00", "Z")
        base_filter: dict[str, str] = {"created_at": f"gte.{cutoff}"}
        if excluded:
            base_filter["id"] = f"not.in.({','.join(str(post_id) for post_id in excluded)})"
        count_query = parse.urlencode({**base_filter, "select": "id"})
        count_endpoint = f"{self.config.url}/rest/v1/community_posts?{count_query}"
        total_data, total_count = self._request_json_with_count(
            count_endpoint,
            method="GET",
            extra_headers={"Prefer": "count=exact"},
        )
        total = total_count if total_count is not None else len(total_data or [])

        # Fetch a larger recent window so reaction/comment summaries can be scored locally.
        recent_limit = max(limit + offset, limit * 4, 40)
        query = parse.urlencode(
            {
                **base_filter,
                "select": "id,user_id,author_name,badge,title,body,preview_type,recording_id,tone,image_urls,image_transforms,created_at,updated_at",
                "order": "created_at.desc,id.desc",
                "limit": str(recent_limit),
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_posts?{query}"
        rows = self._request_json(endpoint, method="GET")
        if not isinstance(rows, list):
            return [], int(total)
        scored_posts = self._posts_from_rows(rows, viewer_user_id)
        scored_posts.sort(
            key=lambda post: (
                int(post.get("likes", 0)) + int(post.get("comments", 0)) * 2,
                str(post.get("created_at", "")),
                int(post.get("id", 0)),
            ),
            reverse=True,
        )
        return scored_posts[offset : offset + limit], int(total)

    def _list_user_posts_rpc(
        self,
        user_id: int,
        limit: int,
        offset: int,
        viewer_user_id: int | None,
    ) -> tuple[list[dict[str, Any]], int] | None:
        data = self._rpc_json(
            "mobile_user_posts",
            {
                "viewer_user_id": int(viewer_user_id or 0),
                "author_user_id": int(user_id),
                "page_limit": int(limit),
                "page_offset": int(offset),
            },
            allow_missing=True,
        )
        return self._posts_with_total_from_rpc_rows(data)

    def _list_following_feed_rpc(
        self,
        limit: int,
        offset: int,
        viewer_user_id: int | None,
    ) -> tuple[list[dict[str, Any]], int] | None:
        if not viewer_user_id:
            return None
        data = self._rpc_json(
            "mobile_following_feed",
            {
                "viewer_user_id": int(viewer_user_id),
                "page_limit": int(limit),
                "page_offset": int(offset),
            },
            allow_missing=True,
        )
        return self._posts_with_total_from_rpc_rows(data)

    def _list_trending_feed_rpc(
        self,
        limit: int,
        offset: int,
        viewer_user_id: int | None,
        exclude_ids: list[int],
    ) -> tuple[list[dict[str, Any]], int] | None:
        if not viewer_user_id:
            return None
        data = self._rpc_json(
            "mobile_trending_feed",
            {
                "viewer_user_id": int(viewer_user_id),
                "page_limit": int(limit),
                "page_offset": int(offset),
                "exclude_ids": [int(post_id) for post_id in exclude_ids if int(post_id) > 0],
            },
            allow_missing=True,
        )
        return self._posts_with_total_from_rpc_rows(data)

    def _posts_with_total_from_rpc_rows(self, data: Any) -> tuple[list[dict[str, Any]], int] | None:
        if not isinstance(data, list):
            return None
        posts = [self._post_from_rpc_row(row) for row in data if isinstance(row, dict)]
        total = 0
        for row in data:
            if isinstance(row, dict):
                try:
                    total = max(total, int(row.get("total_count") or 0))
                except (TypeError, ValueError):
                    continue
        return posts, total

    def _posts_from_rows(self, rows: list[Any], viewer_user_id: int | None) -> list[dict[str, Any]]:
        post_rows = [row for row in rows if isinstance(row, dict)]
        post_ids = [int(row["id"]) for row in post_rows if row.get("id") is not None]
        reaction_summary = self._post_reaction_summary(post_ids, viewer_user_id)
        comment_counts = self._post_comment_counts(post_ids)
        bookmark_summary = self._post_bookmark_summary(post_ids, viewer_user_id)
        author_profiles = self._author_profiles(post_rows)
        return [
            self._post_from_row(
                row,
                author_profile=author_profiles.get(int(row["user_id"])) if row.get("user_id") is not None else None,
                likes=int(reaction_summary.get(int(row["id"]), {}).get("likes", 0)),
                comments=int(comment_counts.get(int(row["id"]), 0)),
                liked_by_me=bool(reaction_summary.get(int(row["id"]), {}).get("liked_by_me", False)),
                bookmarked_by_me=bool(bookmark_summary.get(int(row["id"]), False)),
            )
            for row in post_rows
            if row.get("id") is not None
        ]

    @staticmethod
    def _post_reaction_summary(post_ids: list[int], viewer_user_id: int | None) -> dict[int, dict[str, Any]]:
        repo = configured_supabase_reaction_repository()
        if repo is None:
            return {}
        try:
            return repo.post_reaction_summary(post_ids, viewer_user_id)
        except SupabaseReactionError as exc:
            print(f"WARNING Supabase post reaction summary failed; using zero reaction counts: {exc}")
            return {}

    @staticmethod
    def _post_comment_counts(post_ids: list[int]) -> dict[int, int]:
        repo = configured_supabase_comment_repository()
        if repo is None:
            return {}
        try:
            return repo.comment_counts_for_posts(post_ids)
        except SupabaseCommentError as exc:
            print(f"WARNING Supabase post comment count failed; using zero comment counts: {exc}")
            return {}

    @staticmethod
    def _post_bookmark_summary(post_ids: list[int], viewer_user_id: int | None) -> dict[int, bool]:
        repo = configured_supabase_bookmark_repository()
        if repo is None:
            return {}
        try:
            return repo.post_bookmark_summary(post_ids, viewer_user_id)
        except SupabaseBookmarkError as exc:
            print(f"WARNING Supabase post bookmark summary failed; using false bookmark states: {exc}")
            return {}

    @staticmethod
    def _author_profiles(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        user_ids = [int(row["user_id"]) for row in rows if row.get("user_id") is not None]
        repo = configured_supabase_profile_repository()
        if repo is None:
            return {}
        try:
            return repo.get_profiles(user_ids)
        except SupabaseProfileError as exc:
            print(f"WARNING Supabase author profile read failed; using empty author avatars: {exc}")
            return {}

    def _request_json(
        self,
        endpoint: str,
        *,
        method: str,
        body: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        headers = self._auth_headers()
        headers.update(extra_headers or {})
        req = request.Request(endpoint, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SupabasePostError(f"Supabase post request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabasePostError(f"Supabase post request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabasePostError("Supabase post response was not JSON.") from exc

    def _request_json_with_count(
        self,
        endpoint: str,
        *,
        method: str,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[Any, int | None]:
        headers = self._auth_headers()
        headers.update(extra_headers or {})
        req = request.Request(endpoint, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8", errors="replace")
                total_count = self._parse_content_range_count(response.headers.get("Content-Range", ""))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SupabasePostError(f"Supabase post request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabasePostError(f"Supabase post request failed: {exc}") from exc
        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError as exc:
            raise SupabasePostError("Supabase post response was not JSON.") from exc
        return data, total_count

    def _rpc_json(
        self,
        function_name: str,
        payload: dict[str, Any],
        *,
        allow_missing: bool = False,
    ) -> Any:
        endpoint = f"{self.config.url}/rest/v1/rpc/{function_name}"
        try:
            return self._request_json(
                endpoint,
                method="POST",
                body=json.dumps(payload).encode("utf-8"),
                extra_headers={
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
            )
        except SupabasePostError as exc:
            message = str(exc)
            missing_rpc = "PGRST202" in message or "Could not find the function" in message or "404" in message
            if allow_missing or missing_rpc:
                print(f"WARNING Supabase RPC {function_name} unavailable; using REST fallback: {exc}")
                return None
            raise

    @staticmethod
    def _parse_content_range_count(value: str) -> int | None:
        if "/" not in value:
            return None
        raw_total = value.rsplit("/", 1)[-1]
        if not raw_total.isdigit():
            return None
        return int(raw_total)

    @staticmethod
    def _post_from_row(
        row: dict[str, Any],
        *,
        author_profile: dict[str, Any] | None = None,
        likes: int = 0,
        comments: int = 0,
        liked_by_me: bool = False,
        bookmarked_by_me: bool = False,
    ) -> dict[str, Any]:
        author_avatar_url = str((author_profile or {}).get("avatar_url") or "")
        author_name = str((author_profile or {}).get("username") or row.get("author_name") or "")
        badge = "官方帳號" if author_name.strip().casefold() == "cuevex" else str(row.get("badge") or "")
        return {
            "id": int(row["id"]),
            "user_id": row.get("user_id"),
            "author_name": author_name,
            "author_avatar_url": author_avatar_url,
            "badge": badge,
            "title": str(row.get("title") or ""),
            "body": str(row.get("body") or ""),
            "image_urls": row.get("image_urls") if isinstance(row.get("image_urls"), list) else [],
            "image_transforms": row.get("image_transforms") if isinstance(row.get("image_transforms"), list) else [],
            "preview_type": str(row.get("preview_type") or "pool-table"),
            "recording_id": row.get("recording_id"),
            "tone": str(row.get("tone") or ""),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
            "likes": int(likes),
            "comments": int(comments),
            "shares": 0,
            "liked_by_me": bool(liked_by_me),
            "bookmarked_by_me": bool(bookmarked_by_me),
        }

    @staticmethod
    def _post_from_rpc_row(row: dict[str, Any]) -> dict[str, Any]:
        author_name = str(row.get("author_name") or "")
        return {
            "id": int(row["id"]),
            "user_id": row.get("user_id"),
            "author_name": author_name,
            "author_avatar_url": str(row.get("author_avatar_url") or ""),
            "badge": str(row.get("badge") or ""),
            "title": str(row.get("title") or ""),
            "body": str(row.get("body") or ""),
            "image_urls": row.get("image_urls") if isinstance(row.get("image_urls"), list) else [],
            "image_transforms": row.get("image_transforms") if isinstance(row.get("image_transforms"), list) else [],
            "preview_type": str(row.get("preview_type") or "pool-table"),
            "recording_id": row.get("recording_id"),
            "tone": str(row.get("tone") or ""),
            "created_at": str(row.get("created_at") or ""),
            "updated_at": str(row.get("updated_at") or ""),
            "likes": int(row.get("likes") or 0),
            "comments": int(row.get("comments") or 0),
            "shares": 0,
            "liked_by_me": bool(row.get("liked_by_me")),
            "bookmarked_by_me": bool(row.get("bookmarked_by_me")),
        }

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}


def configured_supabase_post_repository() -> SupabaseCommunityPostRepository | None:
    config = SupabasePostConfig.from_env()
    return SupabaseCommunityPostRepository(config) if config else None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_bigint_id() -> int:
    return int(time.time() * 1000) * 1000 + uuid.uuid4().int % 1000
