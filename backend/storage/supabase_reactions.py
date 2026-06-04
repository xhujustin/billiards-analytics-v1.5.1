import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


class SupabaseReactionError(RuntimeError):
    """Raised when Supabase community reaction sync cannot complete."""


@dataclass(frozen=True)
class SupabaseReactionConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseReactionConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


class SupabaseCommunityReactionRepository:
    def __init__(self, config: SupabaseReactionConfig):
        self.config = config

    def set_post_reaction(self, post_id: int, user_id: int, liked: bool) -> None:
        self._delete_reaction("community_post_reactions", "post_id", post_id, user_id)
        if liked:
            self._insert_reaction("community_post_reactions", "post_id", post_id, user_id)

    def set_comment_reaction(self, comment_id: int, user_id: int, liked: bool) -> None:
        self._delete_reaction("community_comment_reactions", "comment_id", comment_id, user_id)
        if liked:
            self._insert_reaction("community_comment_reactions", "comment_id", comment_id, user_id)

    def post_reaction_summary(self, post_ids: list[int], viewer_user_id: int | None = None) -> dict[int, dict[str, Any]]:
        return self._reaction_summary("community_post_reactions", "post_id", post_ids, viewer_user_id)

    def comment_reaction_summary(self, comment_ids: list[int], viewer_user_id: int | None = None) -> dict[int, dict[str, Any]]:
        return self._reaction_summary("community_comment_reactions", "comment_id", comment_ids, viewer_user_id)

    def _insert_reaction(self, table: str, target_column: str, target_id: int, user_id: int) -> None:
        endpoint = f"{self.config.url}/rest/v1/{table}"
        payload = {
            target_column: int(target_id),
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

    def _delete_reaction(self, table: str, target_column: str, target_id: int, user_id: int) -> None:
        query = parse.urlencode(
            {
                target_column: f"eq.{int(target_id)}",
                "user_id": f"eq.{int(user_id)}",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/{table}?{query}"
        self._request_json(endpoint, method="DELETE")

    def _reaction_summary(
        self,
        table: str,
        target_column: str,
        target_ids: list[int],
        viewer_user_id: int | None,
    ) -> dict[int, dict[str, Any]]:
        ids = sorted({int(target_id) for target_id in target_ids if int(target_id) > 0})
        if not ids:
            return {}
        id_filter = ",".join(str(target_id) for target_id in ids)
        query = parse.urlencode(
            {
                target_column: f"in.({id_filter})",
                "select": f"{target_column},user_id",
            }
        )
        endpoint = f"{self.config.url}/rest/v1/{table}?{query}"
        rows = self._request_json(endpoint, method="GET")
        summary = {target_id: {"likes": 0, "liked_by_me": False} for target_id in ids}
        if not isinstance(rows, list):
            return summary
        viewer_id = int(viewer_user_id or 0)
        seen_pairs: set[tuple[int, int]] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                target_id = int(row[target_column])
                user_id = int(row["user_id"])
            except (KeyError, TypeError, ValueError):
                continue
            pair = (target_id, user_id)
            if pair in seen_pairs or target_id not in summary:
                continue
            seen_pairs.add(pair)
            summary[target_id]["likes"] += 1
            if viewer_id and user_id == viewer_id:
                summary[target_id]["liked_by_me"] = True
        return summary

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
            raise SupabaseReactionError(f"Supabase reaction request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseReactionError(f"Supabase reaction request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseReactionError("Supabase reaction response was not JSON.") from exc

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}


def configured_supabase_reaction_repository() -> SupabaseCommunityReactionRepository | None:
    config = SupabaseReactionConfig.from_env()
    return SupabaseCommunityReactionRepository(config) if config else None
