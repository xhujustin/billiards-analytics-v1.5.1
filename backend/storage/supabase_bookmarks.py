import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseBookmarkError(RuntimeError):
    """Raised when Supabase community bookmark sync cannot complete."""


@dataclass(frozen=True)
class SupabaseBookmarkConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseBookmarkConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseCommunityBookmarkRepository:
    def __init__(self, config: SupabaseBookmarkConfig):
        self.config = config

    def set_post_bookmark(self, post_id: int, user_id: int, bookmarked: bool) -> None:
        self._delete_bookmark(post_id, user_id)
        if bookmarked:
            self._insert_bookmark(post_id, user_id)

    def post_bookmark_summary(self, post_ids: list[int], viewer_user_id: int | None = None) -> dict[int, bool]:
        ids = sorted({int(post_id) for post_id in post_ids if int(post_id) > 0})
        viewer_id = int(viewer_user_id or 0)
        if not ids or not viewer_id:
            return {post_id: False for post_id in ids}
        id_filter = ",".join(str(post_id) for post_id in ids)
        query = parse.urlencode(
            {
                "post_id": f"in.({id_filter})",
                "user_id": f"eq.{viewer_id}",
                "select": "post_id,user_id",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_post_bookmarks?{query}"
        rows = self._request_json(endpoint, method="GET")
        summary = {post_id: False for post_id in ids}
        if not isinstance(rows, list):
            return summary
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                post_id = int(row["post_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if post_id in summary:
                summary[post_id] = True
        return summary

    def list_bookmarked_post_refs(self, user_id: int, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        user_id = int(user_id)
        count_query = parse.urlencode({"user_id": f"eq.{user_id}", "select": "post_id"})
        count_endpoint = f"{self.config.url}/rest/v1/community_post_bookmarks?{count_query}"
        _, total_count = self._request_json_with_count(count_endpoint, method="GET", extra_headers={"Prefer": "count=exact"})
        query = parse.urlencode(
            {
                "user_id": f"eq.{user_id}",
                "select": "post_id,created_at",
                "order": "created_at.desc,post_id.desc",
                "limit": str(limit),
                "offset": str(offset),
            }
        )
        rows = self._request_json(f"{self.config.url}/rest/v1/community_post_bookmarks?{query}", method="GET")
        refs = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
        return refs, int(total_count if total_count is not None else len(refs))

    def _insert_bookmark(self, post_id: int, user_id: int) -> None:
        endpoint = f"{self.config.url}/rest/v1/community_post_bookmarks"
        payload = {
            "post_id": int(post_id),
            "user_id": int(user_id),
        }
        self._request_json(
            endpoint,
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )

    def _delete_bookmark(self, post_id: int, user_id: int) -> None:
        query = parse.urlencode(
            {
                "post_id": f"eq.{int(post_id)}",
                "user_id": f"eq.{int(user_id)}",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/community_post_bookmarks?{query}"
        self._request_json(endpoint, method="DELETE")

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
            raise SupabaseBookmarkError(f"Supabase bookmark request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseBookmarkError(f"Supabase bookmark request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseBookmarkError("Supabase bookmark response was not JSON.") from exc

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
            raise SupabaseBookmarkError(f"Supabase bookmark request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseBookmarkError(f"Supabase bookmark request failed: {exc}") from exc
        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError as exc:
            raise SupabaseBookmarkError("Supabase bookmark response was not JSON.") from exc
        return data, total_count

    @staticmethod
    def _parse_content_range_count(value: str) -> int | None:
        if "/" not in value:
            return None
        raw_total = value.rsplit("/", 1)[-1]
        if raw_total == "*":
            return None
        try:
            return int(raw_total)
        except ValueError:
            return None

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}


def configured_supabase_bookmark_repository() -> SupabaseCommunityBookmarkRepository | None:
    config = SupabaseBookmarkConfig.from_env()
    return SupabaseCommunityBookmarkRepository(config) if config else None
