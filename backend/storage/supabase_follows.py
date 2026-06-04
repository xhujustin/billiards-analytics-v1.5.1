import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseFollowError(RuntimeError):
    """Raised when Supabase user follow sync cannot complete."""


@dataclass(frozen=True)
class SupabaseFollowConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseFollowConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseUserFollowRepository:
    def __init__(self, config: SupabaseFollowConfig):
        self.config = config

    def set_follow(self, follower_user_id: int, following_user_id: int, following: bool) -> None:
        self._delete_follow(follower_user_id, following_user_id)
        if following:
            self._insert_follow(follower_user_id, following_user_id)

    def follow_counts(self, user_id: int) -> dict[str, int]:
        followers = self._count_rows({"following_user_id": f"eq.{int(user_id)}"})
        following = self._count_rows({"follower_user_id": f"eq.{int(user_id)}"})
        return {
            "followers_count": followers,
            "following_count": following,
        }

    def is_following(self, follower_user_id: int, following_user_id: int) -> bool:
        if int(follower_user_id) == int(following_user_id):
            return False
        query = parse.urlencode(
            {
                "follower_user_id": f"eq.{int(follower_user_id)}",
                "following_user_id": f"eq.{int(following_user_id)}",
                "select": "follower_user_id",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/user_follows?{query}"
        rows = self._request_json(endpoint, method="GET")
        return isinstance(rows, list) and bool(rows)

    def list_following_user_ids(self, follower_user_id: int) -> list[int]:
        query = parse.urlencode(
            {
                "follower_user_id": f"eq.{int(follower_user_id)}",
                "select": "following_user_id",
                "order": "created_at.desc",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/user_follows?{query}"
        rows = self._request_json(endpoint, method="GET")
        if not isinstance(rows, list):
            return []
        ids: list[int] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                following_user_id = int(row["following_user_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if following_user_id > 0:
                ids.append(following_user_id)
        return ids

    def _insert_follow(self, follower_user_id: int, following_user_id: int) -> None:
        endpoint = f"{self.config.url}/rest/v1/user_follows"
        payload = {
            "follower_user_id": int(follower_user_id),
            "following_user_id": int(following_user_id),
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

    def _delete_follow(self, follower_user_id: int, following_user_id: int) -> None:
        query = parse.urlencode(
            {
                "follower_user_id": f"eq.{int(follower_user_id)}",
                "following_user_id": f"eq.{int(following_user_id)}",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/user_follows?{query}"
        self._request_json(endpoint, method="DELETE")

    def _count_rows(self, filters: dict[str, str]) -> int:
        params = dict(filters)
        params["select"] = "follower_user_id"
        endpoint = f"{self.config.url}/rest/v1/user_follows?{parse.urlencode(params)}"
        _, total_count = self._request_json_with_count(endpoint, method="GET", extra_headers={"Prefer": "count=exact"})
        return int(total_count or 0)

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
            raise SupabaseFollowError(f"Supabase follow request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseFollowError(f"Supabase follow request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseFollowError("Supabase follow response was not JSON.") from exc

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
            raise SupabaseFollowError(f"Supabase follow request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseFollowError(f"Supabase follow request failed: {exc}") from exc
        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError as exc:
            raise SupabaseFollowError("Supabase follow response was not JSON.") from exc
        return data, total_count

    @staticmethod
    def _parse_content_range_count(value: str) -> int | None:
        if "/" not in value:
            return None
        raw_total = value.rsplit("/", 1)[-1]
        if not raw_total.isdigit():
            return None
        return int(raw_total)

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}


def configured_supabase_follow_repository() -> SupabaseUserFollowRepository | None:
    config = SupabaseFollowConfig.from_env()
    return SupabaseUserFollowRepository(config) if config else None
