import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


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

    def list_comments_for_post(self, post_id: int) -> list[dict[str, Any]]:
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
        return [self._comment_from_row(row) for row in rows if isinstance(row, dict)]

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
        headers = {"apikey": key}
        if not key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {key}"
        return headers

    @staticmethod
    def _comment_from_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "post_id": int(row["post_id"]),
            "user_id": row.get("user_id"),
            "author_name": str(row.get("author_name") or ""),
            "author_avatar_url": "",
            "author_player_level": "",
            "body": str(row.get("body") or ""),
            "created_at": str(row.get("created_at") or ""),
            "likes": 0,
            "liked_by_me": False,
        }


def configured_supabase_comment_repository() -> SupabaseCommunityCommentRepository | None:
    config = SupabaseCommentConfig.from_env()
    return SupabaseCommunityCommentRepository(config) if config else None
