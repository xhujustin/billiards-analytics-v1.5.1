import json
import os
import secrets
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from auth.account_store import (
    AccountError,
    TOKEN_BYTES,
    _hash_secret,
    _hash_token,
    _verify_secret,
    now_ts,
    to_iso_timestamp,
    validate_password,
    validate_username,
)


class SupabaseAccountError(RuntimeError):
    """Raised when Supabase account storage cannot complete a request."""


@dataclass(frozen=True)
class SupabaseAccountConfig:
    url: str
    service_role_key: str

    @classmethod
    def from_env(cls) -> "SupabaseAccountConfig | None":
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not service_role_key:
            return None
        return cls(url=url, service_role_key=service_role_key)


def _user_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": str(row.get("username") or ""),
        "display_name": str(row.get("display_name") or ""),
        "bio": str(row.get("bio") or ""),
        "avatar_url": str(row.get("avatar_url") or ""),
        "is_private": bool(row.get("is_private") or False),
        "is_deactivated": bool(row.get("is_deactivated") or False),
        "security_question": str(row.get("security_question") or ""),
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
    }


class SupabaseAccountStore:
    def __init__(self, config: SupabaseAccountConfig, session_ttl_seconds: int = 7 * 24 * 60 * 60):
        self.config = config
        self.session_ttl_seconds = session_ttl_seconds

    def create_user(self, username: str, password: str, security_question: str, security_answer: str) -> dict[str, Any]:
        normalized_username = validate_username(username)
        validate_password(password)
        question = security_question.strip()
        answer = security_answer.strip()
        if not question:
            raise AccountError("INVALID_SECURITY_QUESTION", "Security question is required.")
        if not answer:
            raise AccountError("INVALID_SECURITY_ANSWER", "Security answer is required.")
        if self._get_user_row_by_username(normalized_username) is not None:
            raise AccountError("USERNAME_TAKEN", "Username is already in use.")

        timestamp = to_iso_timestamp()
        payload = {
            "username": normalized_username,
            "username_key": normalized_username.lower(),
            "password_hash": _hash_secret(password),
            "security_question": question,
            "security_answer_hash": _hash_secret(answer),
            "display_name": "",
            "bio": "",
            "avatar_url": "",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        try:
            row = self._insert_row_with_id_retry("mobile_users", payload)
        except SupabaseAccountError as exc:
            if self._is_unique_key_collision(exc, "username"):
                raise AccountError("USERNAME_TAKEN", "Username is already in use.") from exc
            raise
        return _user_from_row(row)

    def import_user(self, user: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "id": int(user["id"]),
            "username": str(user["username"]),
            "username_key": str(user["username"]).lower(),
            "password_hash": str(user["password_hash"]),
            "security_question": str(user["security_question"]),
            "security_answer_hash": str(user["security_answer_hash"]),
            "display_name": str(user.get("display_name") or ""),
            "bio": str(user.get("bio") or ""),
            "avatar_url": str(user.get("avatar_url") or ""),
            "created_at": str(user["created_at"]),
            "updated_at": str(user["updated_at"]),
        }
        row = self._upsert_row("mobile_users", payload, "id")
        return _user_from_row(row)

    def get_public_user_by_username(self, username: str) -> dict[str, Any] | None:
        row = self._get_user_row_by_username(username)
        return _user_from_row(row) if row else None

    def get_public_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        row = self._get_user_row_by_id(user_id)
        return _user_from_row(row) if row else None

    def login(self, username: str, password: str, device: str = "") -> dict[str, Any]:
        row = self._get_user_row_by_username(username)
        if not row or not _verify_secret(password, str(row.get("password_hash") or "")):
            self.record_login(int(row["id"]) if row else None, username.strip(), "failed", device)
            raise AccountError("INVALID_LOGIN", "Username or password is incorrect.")
        if bool(row.get("is_deactivated") or False):
            row = self._patch_user(
                int(row["id"]),
                {
                    "is_deactivated": False,
                    "deactivated_at": None,
                    "updated_at": to_iso_timestamp(),
                },
            )
        self.record_login(int(row["id"]), str(row["username"]), "success", device)
        return self.create_session(int(row["id"]), _user_from_row(row))

    def create_session(self, user_id: int, user: dict[str, Any] | None = None) -> dict[str, Any]:
        token = secrets.token_urlsafe(TOKEN_BYTES)
        expires_at = now_ts() + self.session_ttl_seconds
        if user is None:
            row = self._get_user_row_by_id(user_id)
            if row is None:
                raise AccountError("USER_NOT_FOUND", "User not found.")
            user = _user_from_row(row)
        payload = {
            "user_id": int(user_id),
            "token_hash": _hash_token(token),
            "expires_at": int(expires_at),
            "created_at": to_iso_timestamp(),
            "revoked_at": None,
        }
        self._insert_row_with_id_retry("mobile_auth_sessions", payload, return_row=False)
        return {"token": token, "user": user, "expires_at": expires_at * 1000}

    def authenticate_token(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        query = parse.urlencode(
            {
                "token_hash": f"eq.{_hash_token(token)}",
                "revoked_at": "is.null",
                "expires_at": f"gt.{now_ts()}",
                "select": "user_id",
                "limit": "1",
            }
        )
        rows = self._request_json(f"{self._table_url('mobile_auth_sessions')}?{query}", method="GET")
        if not isinstance(rows, list) or not rows:
            return None
        try:
            user_id = int(rows[0]["user_id"])
        except (KeyError, TypeError, ValueError):
            return None
        return self.get_public_user_by_id(user_id)

    def revoke_token(self, token: str) -> None:
        query = parse.urlencode({"token_hash": f"eq.{_hash_token(token)}", "revoked_at": "is.null"})
        self._patch_rows("mobile_auth_sessions", query, {"revoked_at": to_iso_timestamp()}, return_rows=False)

    def revoke_other_tokens(self, user_id: int, current_token: str) -> None:
        query = parse.urlencode(
            {
                "user_id": f"eq.{int(user_id)}",
                "token_hash": f"neq.{_hash_token(current_token)}",
                "revoked_at": "is.null",
            }
        )
        self._patch_rows("mobile_auth_sessions", query, {"revoked_at": to_iso_timestamp()}, return_rows=False)

    def record_login(self, user_id: int | None, username: str, status: str, device: str = "") -> None:
        self._insert_row_with_id_retry(
            "mobile_login_history",
            {
                "user_id": int(user_id) if user_id is not None else None,
                "username": username,
                "status": status,
                "device": device,
                "created_at": to_iso_timestamp(),
            },
            return_row=False,
        )

    def import_login_history(self, row: dict[str, Any]) -> None:
        self._upsert_row(
            "mobile_login_history",
            {
                "id": int(row["id"]),
                "user_id": int(row["user_id"]) if row.get("user_id") is not None else None,
                "username": str(row["username"]),
                "status": str(row["status"]),
                "device": str(row.get("device") or ""),
                "created_at": str(row["created_at"]),
            },
            "id",
            return_row=False,
        )

    def get_login_history(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        query = parse.urlencode(
            {
                "user_id": f"eq.{int(user_id)}",
                "select": "created_at,status,device",
                "order": "id.desc",
                "limit": str(limit),
            }
        )
        rows = self._request_json(f"{self._table_url('mobile_login_history')}?{query}", method="GET")
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    def update_username(self, user_id: int, username: str) -> dict[str, Any]:
        normalized_username = validate_username(username)
        existing = self._get_user_row_by_username(normalized_username)
        if existing is not None and int(existing["id"]) != int(user_id):
            raise AccountError("USERNAME_TAKEN", "Username is already in use.")
        row = self._patch_user(
            user_id,
            {
                "username": normalized_username,
                "username_key": normalized_username.lower(),
                "updated_at": to_iso_timestamp(),
            },
        )
        snapshot_query = parse.urlencode({"user_id": f"eq.{int(user_id)}"})
        self._patch_rows("community_posts", snapshot_query, {"author_name": normalized_username}, return_rows=False)
        self._patch_rows("community_comments", snapshot_query, {"author_name": normalized_username}, return_rows=False)
        return _user_from_row(row)

    def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        validate_password(new_password)
        row = self._get_user_row_by_id(user_id)
        if row is None:
            raise AccountError("USER_NOT_FOUND", "User not found.")
        if not _verify_secret(old_password, str(row.get("password_hash") or "")):
            raise AccountError("INVALID_CURRENT_PASSWORD", "Current password is incorrect.")
        self._patch_user(user_id, {"password_hash": _hash_secret(new_password), "updated_at": to_iso_timestamp()})

    def update_security_question(
        self,
        user_id: int,
        current_answer: str,
        security_question: str,
        security_answer: str,
    ) -> dict[str, Any]:
        question = security_question.strip()
        answer = security_answer.strip()
        if not question:
            raise AccountError("INVALID_SECURITY_QUESTION", "Security question is required.")
        if not answer:
            raise AccountError("INVALID_SECURITY_ANSWER", "Security answer is required.")
        row = self._get_user_row_by_id(user_id)
        if row is None:
            raise AccountError("USER_NOT_FOUND", "User not found.")
        if not _verify_secret(current_answer.strip(), str(row.get("security_answer_hash") or "")):
            raise AccountError("INVALID_SECURITY_ANSWER", "Security answer is incorrect.")
        updated = self._patch_user(
            user_id,
            {
                "security_question": question,
                "security_answer_hash": _hash_secret(answer),
                "updated_at": to_iso_timestamp(),
            },
        )
        return _user_from_row(updated)

    def update_mobile_profile(
        self,
        user_id: int,
        display_name: str | None = None,
        bio: str | None = None,
        avatar_url: str | None = None,
        is_private: bool | None = None,
    ) -> dict[str, Any]:
        current = self._get_user_row_by_id(user_id)
        if current is None:
            raise AccountError("USER_NOT_FOUND", "User not found.")
        next_display_name = str(current.get("display_name") or "") if display_name is None else display_name.strip()
        next_bio = str(current.get("bio") or "") if bio is None else bio.strip()
        next_avatar_url = str(current.get("avatar_url") or "") if avatar_url is None else avatar_url.strip()
        if len(next_display_name) > 32:
            raise AccountError("INVALID_DISPLAY_NAME", "Display name must be 32 characters or fewer.")
        if len(next_bio) > 160:
            raise AccountError("INVALID_BIO", "Bio must be 160 characters or fewer.")
        if len(next_avatar_url) > 500:
            raise AccountError("INVALID_AVATAR_URL", "Avatar URL is too long.")
        row = self._patch_user(
            user_id,
            {
                "display_name": next_display_name,
                "bio": next_bio,
                "avatar_url": next_avatar_url,
                "updated_at": to_iso_timestamp(),
            },
        )
        return _user_from_row(row)

    def verify_security_answer(self, username: str, answer: str) -> bool:
        row = self._get_user_row_by_username(username)
        return bool(row and _verify_secret(answer.strip(), str(row.get("security_answer_hash") or "")))

    def reset_password(self, username: str, answer: str, new_password: str) -> None:
        validate_password(new_password)
        row = self._get_user_row_by_username(username)
        if row is None or not _verify_secret(answer.strip(), str(row.get("security_answer_hash") or "")):
            raise AccountError("INVALID_SECURITY_ANSWER", "Security answer is incorrect.")
        self._patch_user(int(row["id"]), {"password_hash": _hash_secret(new_password), "updated_at": to_iso_timestamp()})
        query = parse.urlencode({"user_id": f"eq.{int(row['id'])}", "revoked_at": "is.null"})
        self._patch_rows("mobile_auth_sessions", query, {"revoked_at": to_iso_timestamp()}, return_rows=False)

    def delete_user(self, user_id: int, password: str) -> None:
        row = self._get_user_row_by_id(user_id)
        if row is None:
            raise AccountError("USER_NOT_FOUND", "User not found.")
        if not _verify_secret(password, str(row.get("password_hash") or "")):
            raise AccountError("INVALID_CURRENT_PASSWORD", "Current password is incorrect.")
        query = parse.urlencode({"user_id": f"eq.{int(user_id)}", "revoked_at": "is.null"})
        self._patch_rows("mobile_auth_sessions", query, {"revoked_at": to_iso_timestamp()}, return_rows=False)
        post_ids = self._list_user_post_ids(user_id)
        comment_ids = self._list_comment_ids_for_user_scope(user_id, post_ids)
        if comment_ids:
            self._delete_rows_in("community_comment_reactions", "comment_id", comment_ids)
        if post_ids:
            self._delete_rows_in("community_post_reactions", "post_id", post_ids)
            self._delete_rows_in("community_post_bookmarks", "post_id", post_ids)
            self._delete_rows_in("community_comments", "post_id", post_ids)
            self._delete_rows_in("community_posts", "id", post_ids)
        self._delete_rows("community_comment_reactions", parse.urlencode({"user_id": f"eq.{int(user_id)}"}))
        self._delete_rows("community_post_reactions", parse.urlencode({"user_id": f"eq.{int(user_id)}"}))
        self._delete_rows("community_post_bookmarks", parse.urlencode({"user_id": f"eq.{int(user_id)}"}))
        self._delete_rows("community_comments", parse.urlencode({"user_id": f"eq.{int(user_id)}"}))
        self._delete_rows("user_follows", f"or=(follower_user_id.eq.{int(user_id)},following_user_id.eq.{int(user_id)})")
        self._delete_rows("user_blocks", f"or=(blocker_user_id.eq.{int(user_id)},blocked_user_id.eq.{int(user_id)})")
        self._delete_rows("mobile_profiles", parse.urlencode({"user_id": f"eq.{int(user_id)}"}))
        self._delete_rows("mobile_friend_invite_tokens", f"or=(owner_user_id.eq.{int(user_id)},used_by_user_id.eq.{int(user_id)})")
        self._delete_rows("mobile_friendships", f"or=(user_low_id.eq.{int(user_id)},user_high_id.eq.{int(user_id)})")
        self._request_json(f"{self._table_url('mobile_users')}?{parse.urlencode({'id': f'eq.{int(user_id)}'})}", method="DELETE")

    def deactivate_user(self, user_id: int, password: str) -> None:
        row = self._get_user_row_by_id(user_id)
        if row is None:
            raise AccountError("USER_NOT_FOUND", "User not found.")
        if not _verify_secret(password, str(row.get("password_hash") or "")):
            raise AccountError("INVALID_CURRENT_PASSWORD", "Current password is incorrect.")
        timestamp = to_iso_timestamp()
        self._patch_user(
            user_id,
            {
                "is_deactivated": True,
                "deactivated_at": timestamp,
                "updated_at": timestamp,
            },
        )
        query = parse.urlencode({"user_id": f"eq.{int(user_id)}", "revoked_at": "is.null"})
        self._patch_rows("mobile_auth_sessions", query, {"revoked_at": timestamp}, return_rows=False)

    def create_friend_invite(self, owner_user_id: int, ttl_seconds: int = 10 * 60) -> dict[str, Any]:
        owner = self.get_public_user_by_id(owner_user_id)
        if owner is None:
            raise AccountError("USER_NOT_FOUND", "User not found.")
        token = secrets.token_urlsafe(TOKEN_BYTES)
        expires_at = now_ts() + ttl_seconds
        self._insert_row(
            "mobile_friend_invite_tokens",
            {
                "id": self._next_table_id("mobile_friend_invite_tokens"),
                "owner_user_id": int(owner_user_id),
                "token_hash": _hash_token(token),
                "expires_at": int(expires_at),
                "created_at": to_iso_timestamp(),
                "used_at": None,
                "used_by_user_id": None,
            },
            return_row=False,
        )
        return {"token": token, "expires_at": expires_at * 1000, "owner": owner}

    def are_friends(self, user_a_id: int, user_b_id: int) -> bool:
        if user_a_id == user_b_id:
            return False
        low_id, high_id = sorted((int(user_a_id), int(user_b_id)))
        query = parse.urlencode(
            {
                "user_low_id": f"eq.{low_id}",
                "user_high_id": f"eq.{high_id}",
                "select": "id",
                "limit": "1",
            }
        )
        rows = self._request_json(f"{self._table_url('mobile_friendships')}?{query}", method="GET")
        return isinstance(rows, list) and bool(rows)

    def import_friendship(self, row: dict[str, Any]) -> None:
        self._upsert_row(
            "mobile_friendships",
            {
                "id": int(row["id"]),
                "user_low_id": int(row["user_low_id"]),
                "user_high_id": int(row["user_high_id"]),
                "created_at": str(row["created_at"]),
            },
            "id",
            return_row=False,
        )

    def list_friends(self, user_id: int) -> list[dict[str, Any]]:
        query = parse.urlencode(
            {
                "or": f"(user_low_id.eq.{int(user_id)},user_high_id.eq.{int(user_id)})",
                "select": "id,user_low_id,user_high_id,created_at",
                "order": "id.desc",
            }
        )
        rows = self._request_json(f"{self._table_url('mobile_friendships')}?{query}", method="GET")
        if not isinstance(rows, list):
            return []
        friends: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            friend_id = int(row["user_high_id"]) if int(row["user_low_id"]) == int(user_id) else int(row["user_low_id"])
            friend = self.get_public_user_by_id(friend_id)
            if friend is None:
                continue
            friend["friendship_created_at"] = row["created_at"]
            friends.append(friend)
        return friends

    def accept_friend_invite(self, scanner_user_id: int, token: str) -> dict[str, Any]:
        invite = self._get_invite_row(token)
        if invite is None:
            raise AccountError("INVALID_FRIEND_INVITE", "Friend invite is invalid.")
        if int(invite["expires_at"]) <= now_ts():
            raise AccountError("FRIEND_INVITE_EXPIRED", "Friend invite has expired.")
        owner_user_id = int(invite["owner_user_id"])
        if owner_user_id == int(scanner_user_id):
            raise AccountError("CANNOT_FRIEND_SELF", "You cannot add yourself as a friend.")
        owner = self.get_public_user_by_id(owner_user_id)
        scanner = self.get_public_user_by_id(scanner_user_id)
        if owner is None or scanner is None:
            raise AccountError("USER_NOT_FOUND", "User not found.")

        low_id, high_id = sorted((owner_user_id, int(scanner_user_id)))
        already_friends = self.are_friends(owner_user_id, int(scanner_user_id))
        if not already_friends:
            try:
                self._insert_row(
                    "mobile_friendships",
                    {
                        "id": self._next_table_id("mobile_friendships"),
                        "user_low_id": low_id,
                        "user_high_id": high_id,
                        "created_at": to_iso_timestamp(),
                    },
                    return_row=False,
                )
            except SupabaseAccountError as exc:
                if "23505" not in str(exc) and "duplicate" not in str(exc).lower():
                    raise
                already_friends = True
        if not invite.get("used_at"):
            query = parse.urlencode({"id": f"eq.{int(invite['id'])}", "used_at": "is.null"})
            self._patch_rows(
                "mobile_friend_invite_tokens",
                query,
                {"used_at": to_iso_timestamp(), "used_by_user_id": int(scanner_user_id)},
                return_rows=False,
            )
        return {"friend": owner, "already_friends": already_friends}

    def _get_user_row_by_username(self, username: str) -> dict[str, Any] | None:
        query = parse.urlencode(
            {
                "username_key": f"eq.{username.strip().lower()}",
                "select": "*",
                "limit": "1",
            }
        )
        return self._single_row("mobile_users", query)

    def _get_user_row_by_id(self, user_id: int) -> dict[str, Any] | None:
        query = parse.urlencode({"id": f"eq.{int(user_id)}", "select": "*", "limit": "1"})
        return self._single_row("mobile_users", query)

    def _get_invite_row(self, token: str) -> dict[str, Any] | None:
        query = parse.urlencode({"token_hash": f"eq.{_hash_token(token.strip())}", "select": "*", "limit": "1"})
        return self._single_row("mobile_friend_invite_tokens", query)

    def _next_user_id(self) -> int:
        return self._next_table_id("mobile_users")

    def _next_table_id(self, table: str) -> int:
        query = parse.urlencode({"select": "id", "order": "id.desc", "limit": "1"})
        row = self._single_row(table, query)
        if row is None:
            return 1
        return int(row["id"]) + 1

    def _patch_user(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        row = self._patch_rows("mobile_users", parse.urlencode({"id": f"eq.{int(user_id)}"}), payload)
        if row is None:
            raise AccountError("USER_NOT_FOUND", "User not found.")
        return row

    def _single_row(self, table: str, query: str) -> dict[str, Any] | None:
        rows = self._request_json(f"{self._table_url(table)}?{query}", method="GET")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return rows[0]

    def _insert_row(self, table: str, payload: dict[str, Any], return_row: bool = True) -> dict[str, Any]:
        data = self._request_json(
            self._table_url(table),
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation" if return_row else "return=minimal",
            },
        )
        if not return_row:
            return {}
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise SupabaseAccountError(f"Supabase {table} insert returned no row.")
        return data[0]

    def _insert_row_with_id_retry(
        self,
        table: str,
        payload: dict[str, Any],
        return_row: bool = True,
    ) -> dict[str, Any]:
        try:
            return self._insert_row(table, payload, return_row=return_row)
        except SupabaseAccountError as exc:
            if not self._is_id_sequence_collision(exc) or "id" in payload:
                raise
            retry_payload = {**payload, "id": self._next_table_id(table)}
            return self._insert_row(table, retry_payload, return_row=return_row)

    @staticmethod
    def _is_id_sequence_collision(error: SupabaseAccountError) -> bool:
        message = str(error).lower()
        return "23505" in message and ("key (id)=" in message or "_pkey" in message)

    @staticmethod
    def _is_unique_key_collision(error: SupabaseAccountError, key_fragment: str) -> bool:
        message = str(error).lower()
        return "23505" in message and key_fragment.lower() in message

    def _upsert_row(
        self,
        table: str,
        payload: dict[str, Any],
        conflict_column: str,
        return_row: bool = True,
    ) -> dict[str, Any]:
        endpoint = f"{self._table_url(table)}?on_conflict={parse.quote(conflict_column)}"
        data = self._request_json(
            endpoint,
            method="POST",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": f"resolution=merge-duplicates,{'return=representation' if return_row else 'return=minimal'}",
            },
        )
        if not return_row:
            return {}
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise SupabaseAccountError(f"Supabase {table} upsert returned no row.")
        return data[0]

    def _patch_rows(
        self,
        table: str,
        query: str,
        payload: dict[str, Any],
        return_rows: bool = True,
    ) -> dict[str, Any] | None:
        data = self._request_json(
            f"{self._table_url(table)}?{query}",
            method="PATCH",
            body=json.dumps(payload).encode("utf-8"),
            extra_headers={
                "Content-Type": "application/json",
                "Prefer": "return=representation" if return_rows else "return=minimal",
            },
        )
        if not return_rows:
            return None
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return None
        return data[0]

    def _delete_rows(self, table: str, query: str) -> None:
        self._request_json(f"{self._table_url(table)}?{query}", method="DELETE")

    def _delete_rows_in(self, table: str, column: str, values: list[int]) -> None:
        if not values:
            return
        compact_values = ",".join(str(int(value)) for value in sorted(set(values)))
        self._delete_rows(table, f"{parse.quote(column)}=in.({compact_values})")

    def _list_user_post_ids(self, user_id: int) -> list[int]:
        query = parse.urlencode({"user_id": f"eq.{int(user_id)}", "select": "id"})
        rows = self._request_json(f"{self._table_url('community_posts')}?{query}", method="GET")
        if not isinstance(rows, list):
            return []
        return [int(row["id"]) for row in rows if isinstance(row, dict) and row.get("id") is not None]

    def _list_comment_ids_for_user_scope(self, user_id: int, post_ids: list[int]) -> list[int]:
        queries = [parse.urlencode({"user_id": f"eq.{int(user_id)}", "select": "id"})]
        if post_ids:
            compact_post_ids = ",".join(str(int(value)) for value in sorted(set(post_ids)))
            queries.append(f"post_id=in.({compact_post_ids})&select=id")
        comment_ids: set[int] = set()
        for query in queries:
            rows = self._request_json(f"{self._table_url('community_comments')}?{query}", method="GET")
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get("id") is not None:
                        comment_ids.add(int(row["id"]))
        return sorted(comment_ids)

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
            raise SupabaseAccountError(f"Supabase account request failed with HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise SupabaseAccountError(f"Supabase account request failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseAccountError("Supabase account response was not JSON.") from exc

    def _table_url(self, table: str) -> str:
        return f"{self.config.url}/rest/v1/{table}"

    def _auth_headers(self) -> dict[str, str]:
        key = self.config.service_role_key
        return {"apikey": key, "Authorization": f"Bearer {key}"}


def configured_supabase_account_store(session_ttl_seconds: int = 7 * 24 * 60 * 60) -> SupabaseAccountStore | None:
    config = SupabaseAccountConfig.from_env()
    return SupabaseAccountStore(config, session_ttl_seconds=session_ttl_seconds) if config else None
