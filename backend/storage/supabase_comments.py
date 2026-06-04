import json
import os
from dataclasses import dataclass
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

    def list_comments_for_post(self, post_id: int, viewer_user_id: int | None = None) -> list[dict[str, Any]]:
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
        return {
            "id": int(row["id"]),
            "post_id": int(row["post_id"]),
            "user_id": row.get("user_id"),
            "author_name": str(row.get("author_name") or ""),
            "author_avatar_url": str(profile.get("avatar_url") or ""),
            "author_player_level": str(profile.get("player_level") or ""),
            "body": str(row.get("body") or ""),
            "created_at": str(row.get("created_at") or ""),
            "likes": int(likes),
            "liked_by_me": bool(liked_by_me),
        }


def configured_supabase_comment_repository() -> SupabaseCommunityCommentRepository | None:
    config = SupabaseCommentConfig.from_env()
    return SupabaseCommunityCommentRepository(config) if config else None
