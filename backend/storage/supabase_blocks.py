import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseBlockError(RuntimeError):
    """Raised when Supabase user block sync cannot complete."""


@dataclass(frozen=True)
class SupabaseBlockConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseBlockConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseUserBlockRepository:
    def __init__(self, config: SupabaseBlockConfig):
        self.config = config

    def block_user(self, blocker_user_id: int, blocked_user_id: int) -> dict[str, Any]:
        if int(blocker_user_id) == int(blocked_user_id):
            raise ValueError("Cannot block yourself")
        self._delete_block(blocker_user_id, blocked_user_id)
        self._insert_block(blocker_user_id, blocked_user_id)
        return {
            "blocker_user_id": int(blocker_user_id),
            "blocked_user_id": int(blocked_user_id),
            "is_blocked": True,
        }

    def unblock_user(self, blocker_user_id: int, blocked_user_id: int) -> dict[str, Any]:
        self._delete_block(blocker_user_id, blocked_user_id)
        return {
            "blocker_user_id": int(blocker_user_id),
            "blocked_user_id": int(blocked_user_id),
            "is_blocked": False,
        }

    def block_state(self, viewer_user_id: int, target_user_id: int) -> str:
        if int(viewer_user_id) == int(target_user_id):
            return "none"
        rows = self._list_block_rows(
            f"or=(and(blocker_user_id.eq.{int(viewer_user_id)},blocked_user_id.eq.{int(target_user_id)}),"
            f"and(blocker_user_id.eq.{int(target_user_id)},blocked_user_id.eq.{int(viewer_user_id)}))"
        )
        for row in rows:
            try:
                blocker_id = int(row["blocker_user_id"])
                blocked_id = int(row["blocked_user_id"])
            except (KeyError, TypeError, ValueError):
                continue
            if blocker_id == int(viewer_user_id) and blocked_id == int(target_user_id):
                return "blocked_by_me"
            if blocker_id == int(target_user_id) and blocked_id == int(viewer_user_id):
                return "blocked_me"
        return "none"

    def has_block_between(self, user_a_id: int, user_b_id: int) -> bool:
        return self.block_state(user_a_id, user_b_id) != "none"

    def list_blocked_user_refs(self, blocker_user_id: int) -> list[dict[str, Any]]:
        rows = self._list_block_rows(parse.urlencode({"blocker_user_id": f"eq.{int(blocker_user_id)}"}))
        refs: list[dict[str, Any]] = []
        for row in rows:
            try:
                blocked_user_id = int(row["blocked_user_id"])
            except (KeyError, TypeError, ValueError):
                continue
            refs.append({"user_id": blocked_user_id, "blocked_at": str(row.get("created_at") or "")})
        refs.sort(key=lambda item: str(item.get("blocked_at") or ""), reverse=True)
        return refs

    def related_user_ids(self, user_id: int) -> set[int]:
        rows = self._list_block_rows(
            f"or=(blocker_user_id.eq.{int(user_id)},blocked_user_id.eq.{int(user_id)})"
        )
        ids: set[int] = set()
        for row in rows:
            try:
                blocker_id = int(row["blocker_user_id"])
                blocked_id = int(row["blocked_user_id"])
            except (KeyError, TypeError, ValueError):
                continue
            ids.add(blocker_id)
            ids.add(blocked_id)
        ids.discard(int(user_id))
        return ids

    def _insert_block(self, blocker_user_id: int, blocked_user_id: int) -> None:
        endpoint = f"{self.config.url}/rest/v1/user_blocks"
        payload = {
            "blocker_user_id": int(blocker_user_id),
            "blocked_user_id": int(blocked_user_id),
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

    def _delete_block(self, blocker_user_id: int, blocked_user_id: int) -> None:
        query = parse.urlencode(
            {
                "blocker_user_id": f"eq.{int(blocker_user_id)}",
                "blocked_user_id": f"eq.{int(blocked_user_id)}",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/user_blocks?{query}"
        self._request_json(endpoint, method="DELETE")

    def _list_block_rows(self, query: str) -> list[dict[str, Any]]:
        separator = "&" if query else ""
        endpoint = f"{self.config.url}/rest/v1/user_blocks?{query}{separator}select=blocker_user_id,blocked_user_id,created_at&order=created_at.desc"
        rows = self._request_json(endpoint, method="GET")
        return rows if isinstance(rows, list) else []

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
            raise SupabaseBlockError(f"Supabase block request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseBlockError(f"Supabase block request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseBlockError("Supabase block response was not JSON.") from exc

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}


def configured_supabase_block_repository() -> SupabaseUserBlockRepository | None:
    config = SupabaseBlockConfig.from_env()
    return SupabaseUserBlockRepository(config) if config else None
