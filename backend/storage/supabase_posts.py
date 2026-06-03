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

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        headers = {"apikey": key}
        if not key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {key}"
        return headers


def configured_supabase_post_repository() -> SupabaseCommunityPostRepository | None:
    config = SupabasePostConfig.from_env()
    return SupabaseCommunityPostRepository(config) if config else None
