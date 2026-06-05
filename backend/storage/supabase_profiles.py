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
        data = self._request_profile_rows({"user_id": f"eq.{int(user_id)}"})
        profile = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else None
        users = self._get_user_profiles([user_id])
        return self._merge_profile_with_user(profile, users.get(int(user_id))) if profile or users.get(int(user_id)) else None

    def get_profiles(self, user_ids: list[int]) -> dict[int, dict[str, Any]]:
        ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        if not ids:
            return {}
        id_filter = ",".join(str(user_id) for user_id in ids)
        data = self._request_profile_rows({"user_id": f"in.({id_filter})"})
        if not isinstance(data, list):
            return {}
        profiles: dict[int, dict[str, Any]] = {}
        for row in data:
            if not isinstance(row, dict):
                continue
            try:
                profiles[int(row["user_id"])] = row
            except (KeyError, TypeError, ValueError):
                continue
        users = self._get_user_profiles(ids)
        merged: dict[int, dict[str, Any]] = {}
        for user_id in ids:
            profile = profiles.get(user_id)
            user = users.get(user_id)
            if profile or user:
                merged[user_id] = self._merge_profile_with_user(profile, user)
        return merged

    def _request_profile_rows(self, filters: dict[str, str]) -> Any:
        params = {**filters, "select": "user_id,display_name,bio,avatar_url,is_private,updated_at"}
        endpoint = f"{self.config.url}/rest/v1/mobile_profiles?{parse.urlencode(params)}"
        try:
            return self._request_json(endpoint, method="GET")
        except SupabaseProfileError as exc:
            if "is_private" not in str(exc):
                raise
            fallback_params = {**filters, "select": "user_id,display_name,bio,avatar_url,updated_at"}
            fallback_endpoint = f"{self.config.url}/rest/v1/mobile_profiles?{parse.urlencode(fallback_params)}"
            return self._request_json(fallback_endpoint, method="GET")

    def upsert_profile(self, user_id: int, display_name: str, bio: str, avatar_url: str, is_private: bool | None = None) -> dict[str, Any]:
        endpoint = f"{self.config.url}/rest/v1/mobile_profiles?on_conflict=user_id"
        payload = {
            "user_id": int(user_id),
            "display_name": display_name,
            "bio": bio,
            "avatar_url": avatar_url,
        }
        if is_private is not None:
            payload["is_private"] = bool(is_private)
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

    def update_privacy(self, user_id: int, is_private: bool) -> dict[str, Any]:
        query = parse.urlencode({"user_id": f"eq.{int(user_id)}"})
        endpoint = f"{self.config.url}/rest/v1/mobile_profiles?{query}"
        data = self._request_json(
            endpoint,
            method="PATCH",
            body=json.dumps({"is_private": bool(is_private)}).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
        )
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        user = self._get_user_profiles([int(user_id)]).get(int(user_id), {})
        return self.upsert_profile(int(user_id), str(user.get("display_name") or user.get("username") or ""), str(user.get("bio") or ""), str(user.get("avatar_url") or ""), bool(is_private))

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
        return {"apikey": key, "Authorization": f"Bearer {key}"}

    def _get_user_profiles(self, user_ids: list[int]) -> dict[int, dict[str, Any]]:
        ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        if not ids:
            return {}
        id_filter = ",".join(str(user_id) for user_id in ids)
        query = parse.urlencode(
            {
                "id": f"in.({id_filter})",
                "select": "id,username,display_name,bio,avatar_url,updated_at",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/mobile_users?{query}"
        data = self._request_json(endpoint, method="GET")
        if not isinstance(data, list):
            return {}
        users: dict[int, dict[str, Any]] = {}
        for row in data:
            if not isinstance(row, dict):
                continue
            try:
                users[int(row["id"])] = row
            except (KeyError, TypeError, ValueError):
                continue
        return users

    @staticmethod
    def _merge_profile_with_user(profile: dict[str, Any] | None, user: dict[str, Any] | None) -> dict[str, Any]:
        profile = profile or {}
        user = user or {}
        user_id = profile.get("user_id") or user.get("id")
        return {
            "user_id": user_id,
            "username": str(user.get("username") or ""),
            "display_name": str(profile.get("display_name") or user.get("display_name") or ""),
            "bio": str(profile.get("bio") or user.get("bio") or ""),
            "avatar_url": str(profile.get("avatar_url") or user.get("avatar_url") or ""),
            "is_private": bool(profile.get("is_private") or user.get("is_private") or False),
            "updated_at": profile.get("updated_at") or user.get("updated_at") or "",
        }


def configured_supabase_profile_repository() -> SupabaseMobileProfileRepository | None:
    config = SupabaseProfileConfig.from_env()
    return SupabaseMobileProfileRepository(config) if config else None
