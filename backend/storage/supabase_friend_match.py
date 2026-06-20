import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseFriendMatchError(RuntimeError):
    """Raised when Supabase friend match invite storage fails."""


@dataclass(frozen=True)
class SupabaseFriendMatchConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseFriendMatchConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseFriendMatchRepository:
    def __init__(self, config: SupabaseFriendMatchConfig):
        self.config = config

    def create_invite(
        self,
        *,
        host_player: str,
        game_type: str,
        target_rounds: int,
        shot_time_limit: int,
        ttl_seconds: int,
        qr_payload_factory,
    ) -> dict[str, Any]:
        token = secrets.token_urlsafe(18)
        now = int(time.time())
        expires_at = now + int(ttl_seconds)
        rows = self._request_json(
            self._table_url("friend_match_invites"),
            method="POST",
            body=json.dumps(
                {
                    "token_hash": _hash_token(token),
                    "host_player": host_player,
                    "game_type": game_type,
                    "target_rounds": int(target_rounds),
                    "shot_time_limit": int(shot_time_limit),
                    "status": "pending",
                    "guest_user_id": None,
                    "guest_player": None,
                    "created_at": now,
                    "expires_at": expires_at,
                    "accepted_at": None,
                }
            ).encode("utf-8"),
            extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
        )
        if not isinstance(rows, list) or not rows:
            raise SupabaseFriendMatchError("Supabase friend match invite create returned no row.")
        return _invite_payload(rows[0], token, qr_payload_factory)

    def get_invite(self, token: str, qr_payload_factory) -> dict[str, Any] | None:
        row = self._get_invite_row(token)
        if row is None:
            return None
        payload = _invite_payload(row, token, qr_payload_factory)
        if payload["status"] == "expired" and str(row.get("status") or "") == "pending":
            self._patch_invite(token, {"status": "expired"})
        return payload

    def accept_invite(self, token: str, *, guest_user_id: int, guest_player: str, qr_payload_factory) -> dict[str, Any]:
        row = self._get_invite_row(token)
        if row is None:
            raise KeyError("FRIEND_MATCH_INVITE_NOT_FOUND")
        now = int(time.time())
        status = str(row.get("status") or "pending")
        if status == "pending" and int(row.get("expires_at") or 0) <= now:
            self._patch_invite(token, {"status": "expired"})
            raise ValueError("FRIEND_MATCH_INVITE_EXPIRED")
        if status == "expired":
            raise ValueError("FRIEND_MATCH_INVITE_EXPIRED")
        if str(row.get("host_player") or "").strip().casefold() == guest_player.strip().casefold():
            raise ValueError("INVALID_FRIEND")
        if status == "pending":
            row = self._patch_invite(
                token,
                {
                    "status": "accepted",
                    "guest_user_id": int(guest_user_id),
                    "guest_player": guest_player,
                    "accepted_at": now,
                },
            )
        return _invite_payload(row, token, qr_payload_factory)

    def _get_invite_row(self, token: str) -> dict[str, Any] | None:
        query = parse.urlencode({"token_hash": f"eq.{_hash_token(token.strip())}", "select": "*", "limit": "1"})
        rows = self._request_json(f"{self._table_url('friend_match_invites')}?{query}", method="GET")
        if not isinstance(rows, list) or not rows:
            return None
        return dict(rows[0])

    def _patch_invite(self, token: str, payload: dict[str, Any]) -> dict[str, Any]:
        query = parse.urlencode({"token_hash": f"eq.{_hash_token(token.strip())}"})
        rows = self._request_json(
            f"{self._table_url('friend_match_invites')}?{query}",
            method="PATCH",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
        )
        if not isinstance(rows, list) or not rows:
            raise SupabaseFriendMatchError("Supabase friend match invite update returned no row.")
        return dict(rows[0])

    def _table_url(self, table: str) -> str:
        return f"{self.config.url}/rest/v1/{table}"

    def _request_json(
        self,
        endpoint: str,
        *,
        method: str,
        body: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        headers = {
            "apikey": self.config.service_role_key,
            "Authorization": f"Bearer {self.config.service_role_key}",
        }
        headers.update(extra_headers or {})
        req = request.Request(endpoint, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=20) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SupabaseFriendMatchError(f"Supabase friend match request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseFriendMatchError(f"Supabase friend match request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseFriendMatchError("Supabase friend match response was not JSON.") from exc


def configured_supabase_friend_match_repository() -> SupabaseFriendMatchRepository | None:
    config = SupabaseFriendMatchConfig.from_env()
    return SupabaseFriendMatchRepository(config) if config else None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def _invite_payload(row: dict[str, Any], token: str, qr_payload_factory) -> dict[str, Any]:
    status = str(row.get("status") or "pending")
    expires_at = int(row.get("expires_at") or 0)
    if status == "pending" and expires_at <= int(time.time()):
        status = "expired"
    return {
        "id": int(row.get("id") or 0),
        "token": token,
        "qr_payload": qr_payload_factory(token),
        "host_player": str(row.get("host_player") or ""),
        "game_type": str(row.get("game_type") or "nine_ball"),
        "target_rounds": int(row.get("target_rounds") or 5),
        "shot_time_limit": int(row.get("shot_time_limit") or 0),
        "status": status,
        "guest_user_id": row.get("guest_user_id"),
        "guest_player": row.get("guest_player"),
        "created_at": int(row.get("created_at") or 0),
        "expires_at": expires_at,
        "accepted_at": row.get("accepted_at"),
    }
