import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseProfileError(RuntimeError):
    """Raised when Supabase mobile profile sync cannot complete."""


@dataclass(frozen=True)
class SupabaseProfileConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseProfileConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseMobileProfileRepository:
    def __init__(self, config: SupabaseProfileConfig):
        self.config = config

    def get_profile(self, user_id: int) -> dict[str, Any] | None:
        query = parse.urlencode({"user_id": f"eq.{int(user_id)}", "select": "user_id,display_name,bio,avatar_url,updated_at"})
        endpoint = f"{self.config.url}/rest/v1/mobile_profiles?{query}"
        data = self._request_json(endpoint, method="GET")
        if not isinstance(data, list) or not data:
            return None
        return data[0] if isinstance(data[0], dict) else None

    def upsert_profile(self, user_id: int, display_name: str, bio: str, avatar_url: str) -> dict[str, Any]:
        endpoint = f"{self.config.url}/rest/v1/mobile_profiles?on_conflict=user_id"
        payload = {
            "user_id": int(user_id),
            "display_name": display_name,
            "bio": bio,
            "avatar_url": avatar_url,
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
            raise SupabaseProfileError("Supabase profile upsert returned no row.")
        return data[0]

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
            raise SupabaseProfileError(f"Supabase profile request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseProfileError(f"Supabase profile request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseProfileError("Supabase profile response was not JSON.") from exc

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        headers = {"apikey": key}
        if not key.startswith("sb_"):
            headers["Authorization"] = f"Bearer {key}"
        return headers


def configured_supabase_profile_repository() -> SupabaseMobileProfileRepository | None:
    config = SupabaseProfileConfig.from_env()
    return SupabaseMobileProfileRepository(config) if config else None

