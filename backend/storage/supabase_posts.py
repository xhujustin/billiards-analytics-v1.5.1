import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


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

    def delete_post(self, post_id: int) -> None:
        query = parse.urlencode({"id": f"eq.{int(post_id)}"})
        endpoint = f"{self.config.url}/rest/v1/community_posts?{query}"
        self._request_json(endpoint, method="DELETE")

    def list_posts_for_user(self, user_id: int, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
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
        return [self._post_from_row(row) for row in rows if isinstance(row, dict)], int(total)

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

    @staticmethod
    def _parse_content_range_count(value: str) -> int | None:
        if "/" not in value:
            return None
        raw_total = value.rsplit("/", 1)[-1]
        if not raw_total.isdigit():
            return None
        return int(raw_total)

    @staticmethod
    def _post_from_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "user_id": row.get("user_id"),
            "author_name": str(row.get("author_name") or ""),
            "author_avatar_url": "",
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
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "liked_by_me": False,
            "bookmarked_by_me": False,
        }

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        headers = {"apikey": key}
        if not key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {key}"
        return headers


def configured_supabase_post_repository() -> SupabaseCommunityPostRepository | None:
    config = SupabasePostConfig.from_env()
    return SupabaseCommunityPostRepository(config) if config else None
