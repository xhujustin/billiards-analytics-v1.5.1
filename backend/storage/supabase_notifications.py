import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request


class SupabaseNotificationError(RuntimeError):
    """Raised when Supabase notification settings cannot complete a request."""


@dataclass(frozen=True)
class SupabaseNotificationConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseNotificationConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


DEFAULT_NOTIFICATION_SETTINGS: dict[str, bool] = {
    "push_enabled": True,
    "post_likes_enabled": True,
    "post_comments_enabled": True,
    "comment_replies_enabled": True,
    "comment_likes_enabled": True,
    "new_followers_enabled": True,
    "mutual_follows_enabled": True,
    "account_security_enabled": True,
    "login_changes_enabled": True,
    "service_announcements_enabled": True,
    "show_preview_enabled": True,
    "type_only_enabled": False,
    "quiet_hours_enabled": False,
}

EXPO_PUSH_ENDPOINT = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_ENDPOINT = "https://exp.host/--/api/v2/push/getReceipts"


class SupabaseNotificationRepository:
    def __init__(self, config: SupabaseNotificationConfig):
        self.config = config

    def get_settings(self, user_id: int) -> dict[str, Any]:
        row = self._get_settings_row(user_id)
        if row is None:
            return self._create_default_settings(user_id)
        return self._settings_from_row(row)

    def update_settings(self, user_id: int, updates: dict[str, bool]) -> dict[str, Any]:
        allowed_updates = {key: bool(value) for key, value in updates.items() if key in DEFAULT_NOTIFICATION_SETTINGS}
        if not allowed_updates:
            return self.get_settings(user_id)
        if self._get_settings_row(user_id) is None:
            self._create_default_settings(user_id)
        payload = {
            **allowed_updates,
            "updated_at": _utc_now_iso(),
        }
        row = self._patch_rows("user_notification_settings", parse.urlencode({"user_id": f"eq.{int(user_id)}"}), payload)
        if row is None:
            raise SupabaseNotificationError("Supabase notification settings update returned no row.")
        return self._settings_from_row(row)

    def upsert_push_token(self, user_id: int, expo_push_token: str, device: str = "", platform: str = "") -> dict[str, Any]:
        token = expo_push_token.strip()
        if not token:
            raise ValueError("expo_push_token is required.")
        payload = {
            "user_id": int(user_id),
            "expo_push_token": token,
            "device": device.strip()[:120],
            "platform": platform.strip()[:32],
            "is_active": True,
            "last_seen_at": _utc_now_iso(),
        }
        row = self._upsert_row("user_push_tokens", payload, "user_id,expo_push_token")
        if row is None:
            raise SupabaseNotificationError("Supabase push token upsert returned no row.")
        return row

    def list_active_push_tokens(self, user_id: int) -> list[dict[str, Any]]:
        query = parse.urlencode(
            {
                "user_id": f"eq.{int(user_id)}",
                "is_active": "eq.true",
                "select": "id,user_id,expo_push_token,device,platform,last_seen_at,created_at",
                "order": "last_seen_at.desc",
            }
        )
        rows = self._request_json(f"{self._table_url('user_push_tokens')}?{query}", method="GET")
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def deactivate_push_token(self, expo_push_token: str, error_message: str = "") -> None:
        token = expo_push_token.strip()
        if not token:
            return
        query = parse.urlencode({"expo_push_token": f"eq.{token}"})
        payload = {
            "is_active": False,
            "last_seen_at": _utc_now_iso(),
        }
        if error_message:
            payload["device"] = f"inactive:{error_message[:100]}"
        self._patch_rows("user_push_tokens", query, payload)

    def create_event(
        self,
        *,
        recipient_user_id: int,
        actor_user_id: int,
        event_type: str,
        source_type: str,
        source_id: int,
        title: str,
        body: str,
        status: str = "pending",
        error_message: str = "",
    ) -> dict[str, Any]:
        payload = {
            "recipient_user_id": int(recipient_user_id),
            "actor_user_id": int(actor_user_id),
            "event_type": event_type,
            "source_type": source_type,
            "source_id": int(source_id),
            "title": title,
            "body": body,
            "status": status,
            "error": error_message,
        }
        row = self._insert_row("user_notification_events", payload)
        if row is None:
            raise SupabaseNotificationError("Supabase notification event insert returned no row.")
        return row

    def mark_event_sent(self, event_id: int, ticket_ids: list[str] | None = None) -> None:
        payload: dict[str, Any] = {"status": "sent", "sent_at": _utc_now_iso(), "error": ""}
        if ticket_ids is not None:
            payload["expo_ticket_ids"] = ticket_ids
        try:
            self._patch_rows("user_notification_events", parse.urlencode({"id": f"eq.{int(event_id)}"}), payload)
        except SupabaseNotificationError:
            payload.pop("expo_ticket_ids", None)
            self._patch_rows("user_notification_events", parse.urlencode({"id": f"eq.{int(event_id)}"}), payload)

    def mark_event_failed(self, event_id: int, error_message: str) -> None:
        self._patch_rows(
            "user_notification_events",
            parse.urlencode({"id": f"eq.{int(event_id)}"}),
            {"status": "failed", "error": error_message[:500]},
        )

    def list_recent_events(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 50))
        query = parse.urlencode(
            {
                "recipient_user_id": f"eq.{int(user_id)}",
                "select": "id,recipient_user_id,actor_user_id,event_type,source_type,source_id,title,body,status,error,created_at,sent_at,expo_ticket_ids,expo_receipts,receipt_checked_at",
                "order": "created_at.desc",
                "limit": str(safe_limit),
            }
        )
        rows = self._request_json(f"{self._table_url('user_notification_events')}?{query}", method="GET")
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def list_recent_sent_events(self, limit: int = 10) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 20))
        query = parse.urlencode(
            {
                "status": "eq.sent",
                "select": "id,recipient_user_id,actor_user_id,event_type,status,error,created_at,sent_at,expo_ticket_ids,expo_receipts,receipt_checked_at",
                "order": "created_at.desc",
                "limit": str(safe_limit),
            }
        )
        rows = self._request_json(f"{self._table_url('user_notification_events')}?{query}", method="GET")
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def mark_event_receipts(self, event_id: int, receipts: dict[str, Any]) -> None:
        errors: list[str] = []
        for receipt in receipts.values():
            if not isinstance(receipt, dict) or receipt.get("status") == "ok":
                continue
            details = receipt.get("details") if isinstance(receipt.get("details"), dict) else {}
            errors.append(str(details.get("error") or receipt.get("message") or "unknown"))
        payload: dict[str, Any] = {
            "expo_receipts": receipts,
            "receipt_checked_at": _utc_now_iso(),
        }
        if errors:
            payload["status"] = "failed"
            payload["error"] = ",".join(errors)[:500]
        self._patch_rows("user_notification_events", parse.urlencode({"id": f"eq.{int(event_id)}"}), payload)

    def _get_settings_row(self, user_id: int) -> dict[str, Any] | None:
        query = parse.urlencode({"user_id": f"eq.{int(user_id)}", "select": "*", "limit": "1"})
        rows = self._request_json(f"{self._table_url('user_notification_settings')}?{query}", method="GET")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return rows[0]

    def _create_default_settings(self, user_id: int) -> dict[str, Any]:
        payload = {
            "user_id": int(user_id),
            **DEFAULT_NOTIFICATION_SETTINGS,
        }
        row = self._insert_row("user_notification_settings", payload)
        if row is None:
            raise SupabaseNotificationError("Supabase notification settings insert returned no row.")
        return self._settings_from_row(row)

    @staticmethod
    def _settings_from_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "user_id": int(row["user_id"]),
            **{key: bool(row.get(key)) for key in DEFAULT_NOTIFICATION_SETTINGS},
            "updated_at": str(row.get("updated_at") or ""),
        }

    def _insert_row(self, table: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        data = self._request_json(
            self._table_url(table),
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
        )
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        return data[0]

    def _upsert_row(self, table: str, payload: dict[str, Any], conflict_columns: str) -> dict[str, Any] | None:
        data = self._request_json(
            f"{self._table_url(table)}?on_conflict={parse.quote(conflict_columns, safe=',')}",
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=representation",
            },
        )
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        return data[0]

    def _patch_rows(self, table: str, query: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        data = self._request_json(
            f"{self._table_url(table)}?{query}",
            method="PATCH",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={"Content-Type": "application/json", "Prefer": "return=representation"},
        )
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
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
            raise SupabaseNotificationError(f"Supabase notification request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseNotificationError(f"Supabase notification request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseNotificationError("Supabase notification response was not JSON.") from exc

    def _table_url(self, table: str) -> str:
        return f"{self.config.url}/rest/v1/{table}"

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}


class ExpoPushClient:
    def send(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not messages:
            return []
        req = request.Request(
            EXPO_PUSH_ENDPOINT,
            data=json.dumps(messages).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=12) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SupabaseNotificationError(f"Expo push request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseNotificationError(f"Expo push request failed: {exc}") from exc
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise SupabaseNotificationError("Expo push response was not JSON.") from exc
        tickets = data.get("data") if isinstance(data, dict) else None
        return [ticket for ticket in tickets if isinstance(ticket, dict)] if isinstance(tickets, list) else []

    def get_receipts(self, ticket_ids: list[str]) -> dict[str, Any]:
        ids = [ticket_id for ticket_id in ticket_ids if ticket_id]
        if not ids:
            return {}
        req = request.Request(
            EXPO_RECEIPTS_ENDPOINT,
            data=json.dumps({"ids": ids}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=12) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise SupabaseNotificationError(f"Expo receipt request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseNotificationError(f"Expo receipt request failed: {exc}") from exc
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise SupabaseNotificationError("Expo receipt response was not JSON.") from exc
        receipts = data.get("data") if isinstance(data, dict) else None
        return receipts if isinstance(receipts, dict) else {}


def configured_supabase_notification_repository() -> SupabaseNotificationRepository | None:
    config = SupabaseNotificationConfig.from_env()
    return SupabaseNotificationRepository(config) if config else None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
