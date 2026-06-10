from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from storage.supabase_notifications import (
    DEFAULT_NOTIFICATION_SETTINGS,
    ExpoPushClient,
    SupabaseNotificationError,
    SupabaseNotificationRepository,
    configured_supabase_notification_repository,
)


NOTIFICATION_SETTING_BY_EVENT = {
    "post_liked": "post_likes_enabled",
    "post_commented": "post_comments_enabled",
    "comment_liked": "comment_likes_enabled",
    "new_follower": "new_followers_enabled",
    "mutual_follow": "mutual_follows_enabled",
}


@dataclass(frozen=True)
class MobilePushEvent:
    recipient_user_id: int
    actor_user_id: int
    event_type: str
    source_type: str
    source_id: int
    title: str
    body: str
    data: dict[str, Any]


class MobilePushNotificationService:
    def __init__(
        self,
        repository: SupabaseNotificationRepository,
        push_client: ExpoPushClient | None = None,
    ):
        self.repository = repository
        self.push_client = push_client or ExpoPushClient()

    def dispatch(self, event: MobilePushEvent) -> dict[str, Any]:
        if int(event.recipient_user_id) <= 0 or int(event.actor_user_id) <= 0:
            return {"status": "skipped", "reason": "invalid_user"}
        if int(event.recipient_user_id) == int(event.actor_user_id) and event.event_type != "test_push":
            return {"status": "skipped", "reason": "self_event"}

        settings = self.repository.get_settings(int(event.recipient_user_id))
        if not self._event_enabled(settings, event.event_type):
            self.repository.create_event(
                recipient_user_id=event.recipient_user_id,
                actor_user_id=event.actor_user_id,
                event_type=event.event_type,
                source_type=event.source_type,
                source_id=event.source_id,
                title=event.title,
                body=event.body,
                status="skipped",
                error_message="disabled_by_settings",
            )
            return {"status": "skipped", "reason": "disabled_by_settings"}

        tokens = self.repository.list_active_push_tokens(int(event.recipient_user_id))
        notification_event = self.repository.create_event(
            recipient_user_id=event.recipient_user_id,
            actor_user_id=event.actor_user_id,
            event_type=event.event_type,
            source_type=event.source_type,
            source_id=event.source_id,
            title=event.title,
            body=event.body,
        )
        if not tokens:
            self.repository.mark_event_failed(int(notification_event["id"]), "no_active_push_tokens")
            return {"status": "failed", "reason": "no_active_push_tokens"}

        messages = [
            {
                "to": str(token["expo_push_token"]),
                "sound": "default",
                "channelId": "default",
                "priority": "high",
                "title": event.title,
                "body": event.body if bool(settings.get("show_preview_enabled", True)) else self._type_only_body(event.event_type),
                "data": {
                    **event.data,
                    "event_type": event.event_type,
                    "source_type": event.source_type,
                    "source_id": event.source_id,
                },
            }
            for token in tokens
            if str(token.get("expo_push_token") or "").startswith("ExponentPushToken[")
            or str(token.get("expo_push_token") or "").startswith("ExpoPushToken[")
        ]
        if not messages:
            self.repository.mark_event_failed(int(notification_event["id"]), "no_valid_expo_push_tokens")
            return {"status": "failed", "reason": "no_valid_expo_push_tokens"}

        try:
            tickets = self.push_client.send(messages)
        except SupabaseNotificationError as exc:
            self.repository.mark_event_failed(int(notification_event["id"]), str(exc))
            return {"status": "failed", "reason": str(exc)}

        ticket_ids = [str(ticket.get("id") or "") for ticket in tickets if ticket.get("id")]
        errors: list[str] = []
        for token, ticket in zip(tokens, tickets):
            if ticket.get("status") == "ok":
                continue
            details = ticket.get("details") if isinstance(ticket.get("details"), dict) else {}
            error_code = str(details.get("error") or ticket.get("message") or "unknown")
            errors.append(error_code)
            if error_code in {"DeviceNotRegistered", "InvalidCredentials"}:
                self.repository.deactivate_push_token(str(token.get("expo_push_token") or ""), error_code)
        if errors:
            self.repository.mark_event_failed(int(notification_event["id"]), ",".join(errors))
            return {"status": "failed", "reason": ",".join(errors)}

        self.repository.mark_event_sent(int(notification_event["id"]), ticket_ids)
        return {"status": "sent", "tickets": len(tickets), "ticket_ids": ticket_ids}

    def check_receipts_for_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event_id = int(event.get("id") or 0)
        ticket_ids = event.get("expo_ticket_ids") if isinstance(event.get("expo_ticket_ids"), list) else []
        if event_id <= 0 or not ticket_ids:
            return {"event_id": event_id, "status": "skipped", "reason": "no_ticket_ids"}
        try:
            receipts = self.push_client.get_receipts([str(ticket_id) for ticket_id in ticket_ids])
        except SupabaseNotificationError as exc:
            return {"event_id": event_id, "status": "failed", "reason": str(exc)}
        self.repository.mark_event_receipts(event_id, receipts)
        return {"event_id": event_id, "status": "checked", "receipts": receipts}

    @staticmethod
    def _event_enabled(settings: dict[str, Any], event_type: str) -> bool:
        if not bool(settings.get("push_enabled", DEFAULT_NOTIFICATION_SETTINGS["push_enabled"])):
            return False
        key = NOTIFICATION_SETTING_BY_EVENT.get(event_type)
        if key is None:
            return True
        return bool(settings.get(key, DEFAULT_NOTIFICATION_SETTINGS.get(key, True)))

    @staticmethod
    def _type_only_body(event_type: str) -> str:
        clean_labels = {
            "post_liked": "貼文互動",
            "post_commented": "貼文互動",
            "comment_liked": "留言互動",
            "new_follower": "追蹤與好友",
            "mutual_follow": "追蹤與好友",
        }
        return clean_labels.get(event_type, "通知")
        labels = {
            "post_liked": "貼文互動",
            "post_commented": "貼文互動",
            "comment_liked": "留言互動",
            "new_follower": "追蹤與好友",
            "mutual_follow": "追蹤與好友",
        }
        return labels.get(event_type, "通知")


def configured_mobile_push_notification_service() -> MobilePushNotificationService | None:
    repository = configured_supabase_notification_repository()
    if repository is None:
        return None
    return MobilePushNotificationService(repository)
