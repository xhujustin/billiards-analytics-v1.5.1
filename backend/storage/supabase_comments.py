import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request

from storage.supabase_profiles import SupabaseProfileError, configured_supabase_profile_repository
from storage.supabase_reactions import SupabaseReactionError, configured_supabase_reaction_repository


class SupabaseCommentError(RuntimeError):
    """Raised when Supabase community comment sync cannot complete."""


@dataclass(frozen=True)
class SupabaseCommentConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseCommentConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseCommunityCommentRepository:
    def __init__(self, config: SupabaseCommentConfig):
        self.config = config

    def create_comment(self, comment: dict[str, Any], viewer_user_id: int | None = None) -> dict[str, Any]:
        if viewer_user_id:
            rpc_result = self.create_comment_rpc(
                int(comment["post_id"]),
                int(viewer_user_id),
                str(comment.get("body") or ""),
            )
            if rpc_result is not None:
                return rpc_result["comment"]
        payload = {
            "id": int(comment.get("id") or _new_bigint_id()),
            "post_id": int(comment["post_id"]),
            "user_id": int(comment["user_id"]) if comment.get("user_id") is not None else None,
            "author_name": str(comment.get("author_name") or ""),
            "body": str(comment.get("body") or ""),
            "created_at": str(comment.get("created_at") or _utc_now_iso()),
        }
        row = self._insert_comment_row(payload)
        return self._comment_from_row_with_summaries(row, viewer_user_id)

    def upsert_comment(self, comment: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self.config.url}/rest/v1/community_comments?on_conflict=id"
        payload = {
            "id": int(comment["id"]),
            "post_id": int(comment["post_id"]),
            "user_id": int(comment["user_id"]) if comment.get("user_id") is not None else None,
            "author_name": str(comment.get("author_name") or ""),
            "body": str(comment.get("body") or ""),
            "created_at": comment["created_at"],
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
            raise SupabaseCommentError("Supabase comment upsert returned no row.")
        return data[0]

    def get_comment(self, comment_id: int, viewer_user_id: int | None = None) -> dict[str, Any] | None:
        rpc_comments = self.hydrated_comments([comment_id], viewer_user_id)
        if rpc_comments:
            return rpc_comments[0]
        query = parse.urlencode(
            {
                "id": f"eq.{int(comment_id)}",
                "select": "id,post_id,user_id,author_name,body,created_at",
                "limit": "1",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_comments?{query}"
        rows = self._request_json(endpoint, method="GET")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return self._comment_from_row_with_summaries(rows[0], viewer_user_id)

    def list_comments_for_post(self, post_id: int, viewer_user_id: int | None = None) -> list[dict[str, Any]]:
        rpc_comments = self.list_comments_for_post_rpc(post_id, viewer_user_id)
        if rpc_comments is not None:
            return rpc_comments
        query = parse.urlencode(
            {
                "post_id": f"eq.{int(post_id)}",
                "select": "id,post_id,user_id,author_name,body,created_at",
                "order": "created_at.asc,id.asc",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_comments?{query}"
        rows = self._request_json(endpoint, method="GET")
        if not isinstance(rows, list):
            return []
        comment_rows = [row for row in rows if isinstance(row, dict)]
        comment_ids = [int(row["id"]) for row in comment_rows if row.get("id") is not None]
        reaction_summary = self._comment_reaction_summary(comment_ids, viewer_user_id)
        author_profiles = self._author_profiles(comment_rows)
        return [
            self._comment_from_row(
                row,
                author_profile=author_profiles.get(int(row["user_id"])) if row.get("user_id") is not None else None,
                likes=int(reaction_summary.get(int(row["id"]), {}).get("likes", 0)),
                liked_by_me=bool(reaction_summary.get(int(row["id"]), {}).get("liked_by_me", False)),
            )
            for row in comment_rows
            if row.get("id") is not None
        ]

    def hydrated_comments(self, comment_ids: list[int], viewer_user_id: int | None = None) -> list[dict[str, Any]]:
        ids = [int(comment_id) for comment_id in comment_ids if int(comment_id) > 0]
        if not ids:
            return []
        data = self._rpc_json(
            "mobile_hydrated_comments",
            {
                "viewer_user_id": int(viewer_user_id or 0),
                "comment_ids": ids,
            },
            allow_missing=True,
        )
        if not isinstance(data, list):
            return []
        comments = [self._comment_from_rpc_row(row) for row in data if isinstance(row, dict)]
        order = {comment_id: index for index, comment_id in enumerate(ids)}
        comments.sort(key=lambda comment: order.get(int(comment.get("id") or 0), len(order)))
        return comments

    def list_comments_for_post_rpc(self, post_id: int, viewer_user_id: int | None = None) -> list[dict[str, Any]] | None:
        data = self._rpc_json(
            "mobile_comments_for_post",
            {
                "viewer_user_id": int(viewer_user_id or 0),
                "target_post_id": int(post_id),
            },
            allow_missing=True,
        )
        if not isinstance(data, list):
            return None
        return [self._comment_from_rpc_row(row) for row in data if isinstance(row, dict)]

    def create_comment_rpc(self, post_id: int, viewer_user_id: int, body: str) -> dict[str, Any] | None:
        data = self._rpc_json(
            "mobile_create_comment",
            {
                "viewer_user_id": int(viewer_user_id),
                "target_post_id": int(post_id),
                "comment_body": str(body),
            },
            allow_missing=True,
        )
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if not isinstance(row, dict):
                continue
            comment = row.get("comment")
            post = row.get("post")
            if isinstance(comment, dict):
                return {
                    "comment": self._comment_from_rpc_row(comment),
                    "post": post if isinstance(post, dict) else None,
                }
        return None

    def toggle_comment_like(self, comment_id: int, viewer_user_id: int) -> dict[str, Any] | None:
        data = self._rpc_json(
            "mobile_toggle_comment_like",
            {
                "viewer_user_id": int(viewer_user_id),
                "target_comment_id": int(comment_id),
            },
            allow_missing=True,
        )
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if isinstance(row, dict):
                return self._comment_from_rpc_row(row)
        return None

    def comment_counts_for_posts(self, post_ids: list[int]) -> dict[int, int]:
        ids = sorted({int(post_id) for post_id in post_ids if int(post_id) > 0})
        if not ids:
            return {}
        id_filter = ",".join(str(post_id) for post_id in ids)
        query = parse.urlencode(
            {
                "post_id": f"in.({id_filter})",
                "select": "post_id,id",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_comments?{query}"
        rows = self._request_json(endpoint, method="GET")
        counts = {post_id: 0 for post_id in ids}
        if not isinstance(rows, list):
            return counts
        seen_comments: set[int] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                post_id = int(row["post_id"])
                comment_id = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if comment_id in seen_comments or post_id not in counts:
                continue
            seen_comments.add(comment_id)
            counts[post_id] += 1
        return counts

    def _insert_comment_row(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self.config.url}/rest/v1/community_comments"
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
            raise SupabaseCommentError("Supabase comment create returned no row.")
        return data[0]

    def _comment_from_row_with_summaries(self, row: dict[str, Any], viewer_user_id: int | None) -> dict[str, Any]:
        comment_id = int(row["id"])
        reaction_summary = self._comment_reaction_summary([comment_id], viewer_user_id)
        author_profiles = self._author_profiles([row])
        return self._comment_from_row(
            row,
            author_profile=author_profiles.get(int(row["user_id"])) if row.get("user_id") is not None else None,
            likes=int(reaction_summary.get(comment_id, {}).get("likes", 0)),
            liked_by_me=bool(reaction_summary.get(comment_id, {}).get("liked_by_me", False)),
        )

    @staticmethod
    def _comment_reaction_summary(comment_ids: list[int], viewer_user_id: int | None) -> dict[int, dict[str, Any]]:
        repo = configured_supabase_reaction_repository()
        if repo is None:
            return {}
        try:
            return repo.comment_reaction_summary(comment_ids, viewer_user_id)
        except SupabaseReactionError as exc:
            print(f"WARNING Supabase comment reaction summary failed; using zero reaction counts: {exc}")
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
            print(f"WARNING Supabase comment author profile read failed; using empty author avatars: {exc}")
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
            raise SupabaseCommentError(f"Supabase comment request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseCommentError(f"Supabase comment request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseCommentError("Supabase comment response was not JSON.") from exc

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
        except SupabaseCommentError as exc:
            message = str(exc)
            missing_rpc = "PGRST202" in message or "Could not find the function" in message or "404" in message
            if allow_missing or missing_rpc:
                print(f"WARNING Supabase RPC {function_name} unavailable; using REST fallback: {exc}")
                return None
            raise

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}

    @staticmethod
    def _comment_from_row(
        row: dict[str, Any],
        *,
        author_profile: dict[str, Any] | None = None,
        likes: int = 0,
        liked_by_me: bool = False,
    ) -> dict[str, Any]:
        profile = author_profile or {}
        author_name = str(profile.get("username") or row.get("author_name") or "")
        return {
            "id": int(row["id"]),
            "post_id": int(row["post_id"]),
            "user_id": row.get("user_id"),
            "author_name": author_name,
            "author_avatar_url": str(profile.get("avatar_url") or ""),
            "author_player_level": "官方帳號" if author_name.strip().casefold() == "cuevex" else str(profile.get("player_level") or ""),
            "body": str(row.get("body") or ""),
            "created_at": str(row.get("created_at") or ""),
            "likes": int(likes),
            "liked_by_me": bool(liked_by_me),
        }

    @staticmethod
    def _comment_from_rpc_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "post_id": int(row["post_id"]),
            "user_id": row.get("user_id"),
            "author_name": str(row.get("author_name") or ""),
            "author_avatar_url": str(row.get("author_avatar_url") or ""),
            "author_player_level": str(row.get("author_player_level") or ""),
            "body": str(row.get("body") or ""),
            "created_at": str(row.get("created_at") or ""),
            "likes": int(row.get("likes") or 0),
            "liked_by_me": bool(row.get("liked_by_me")),
        }


def configured_supabase_comment_repository() -> SupabaseCommunityCommentRepository | None:
    config = SupabaseCommentConfig.from_env()
    return SupabaseCommunityCommentRepository(config) if config else None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_bigint_id() -> int:
    return int(time.time() * 1000) * 1000 + uuid.uuid4().int % 1000
