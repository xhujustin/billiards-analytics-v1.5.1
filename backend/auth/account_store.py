import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
PASSWORD_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
PBKDF2_ITERATIONS = 210_000
TOKEN_BYTES = 32


class AccountError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def now_ts() -> int:
    return int(time.time())


def to_iso_timestamp(timestamp: int | float | None = None) -> str:
    value = now_ts() if timestamp is None else timestamp
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def validate_username(username: str) -> str:
    normalized = username.strip()
    if len(normalized) < 3 or len(normalized) > 32 or not USERNAME_PATTERN.fullmatch(normalized):
        raise AccountError("INVALID_USERNAME", "Username must be 3-32 letters, numbers, or underscore.")
    return normalized


def validate_password(password: str) -> None:
    if (
        len(password) < 10
        or not PASSWORD_PATTERN.fullmatch(password)
        or not any(char.isalpha() for char in password)
        or not any(char.isdigit() for char in password)
    ):
        raise AccountError(
            "INVALID_PASSWORD",
            "Password must be at least 10 characters and contain only letters and numbers, including both.",
        )


def _hash_secret(secret: str, salt: bytes | None = None) -> str:
    secret_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), secret_salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${secret_salt.hex()}${digest.hex()}"


def _verify_secret(secret: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            secret.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations_raw),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "security_question": row["security_question"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class AccountStore:
    def __init__(self, db_path: str, session_ttl_seconds: int = 7 * 24 * 60 * 60):
        self.db_path = db_path
        self.session_ttl_seconds = session_ttl_seconds
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self) -> None:
        with self.transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    security_question TEXT NOT NULL,
                    security_answer_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS login_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('success', 'failed')),
                    device TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_login_history_user ON login_history(user_id, id DESC)")

    def create_user(self, username: str, password: str, security_question: str, security_answer: str) -> dict[str, Any]:
        normalized_username = validate_username(username)
        validate_password(password)
        question = security_question.strip()
        answer = security_answer.strip()
        if not question:
            raise AccountError("INVALID_SECURITY_QUESTION", "Security question is required.")
        if not answer:
            raise AccountError("INVALID_SECURITY_ANSWER", "Security answer is required.")

        timestamp = to_iso_timestamp()
        try:
            with self.transaction() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO users (
                        username, password_hash, security_question, security_answer_hash, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized_username,
                        _hash_secret(password),
                        question,
                        _hash_secret(answer),
                        timestamp,
                        timestamp,
                    ),
                )
                user_id = int(cursor.lastrowid)
                row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                return _row_to_user(row)
        except sqlite3.IntegrityError as exc:
            raise AccountError("USERNAME_TAKEN", "Username is already in use.") from exc

    def get_user_by_username(self, username: str) -> sqlite3.Row | None:
        with self.transaction() as conn:
            return conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)).fetchone()

    def get_public_user_by_username(self, username: str) -> dict[str, Any] | None:
        row = self.get_user_by_username(username)
        return _row_to_user(row) if row else None

    def login(self, username: str, password: str, device: str = "") -> dict[str, Any]:
        row = self.get_user_by_username(username)
        if not row or not _verify_secret(password, row["password_hash"]):
            self.record_login(row["id"] if row else None, username.strip(), "failed", device)
            raise AccountError("INVALID_LOGIN", "Username or password is incorrect.")

        self.record_login(row["id"], row["username"], "success", device)
        return self.create_session(int(row["id"]), _row_to_user(row))

    def create_session(self, user_id: int, user: dict[str, Any] | None = None) -> dict[str, Any]:
        token = secrets.token_urlsafe(TOKEN_BYTES)
        expires_at = now_ts() + self.session_ttl_seconds
        with self.transaction() as conn:
            if user is None:
                row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                if row is None:
                    raise AccountError("USER_NOT_FOUND", "User not found.")
                user = _row_to_user(row)
            conn.execute(
                """
                INSERT INTO auth_sessions (user_id, token_hash, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, _hash_token(token), expires_at, to_iso_timestamp()),
            )
        return {"token": token, "user": user, "expires_at": expires_at * 1000}

    def authenticate_token(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        with self.transaction() as conn:
            row = conn.execute(
                """
                SELECT users.*
                FROM auth_sessions
                JOIN users ON users.id = auth_sessions.user_id
                WHERE auth_sessions.token_hash = ?
                  AND auth_sessions.revoked_at IS NULL
                  AND auth_sessions.expires_at > ?
                """,
                (_hash_token(token), now_ts()),
            ).fetchone()
            return _row_to_user(row) if row else None

    def revoke_token(self, token: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                (to_iso_timestamp(), _hash_token(token)),
            )

    def record_login(self, user_id: int | None, username: str, status: str, device: str = "") -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO login_history (user_id, username, status, device, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, status, device, to_iso_timestamp()),
            )

    def get_login_history(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self.transaction() as conn:
            rows = conn.execute(
                """
                SELECT created_at, status, device
                FROM login_history
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def update_username(self, user_id: int, username: str) -> dict[str, Any]:
        normalized_username = validate_username(username)
        with self.transaction() as conn:
            try:
                conn.execute(
                    "UPDATE users SET username = ?, updated_at = ? WHERE id = ?",
                    (normalized_username, to_iso_timestamp(), user_id),
                )
            except sqlite3.IntegrityError as exc:
                raise AccountError("USERNAME_TAKEN", "Username is already in use.") from exc
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                raise AccountError("USER_NOT_FOUND", "User not found.")
            return _row_to_user(row)

    def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        validate_password(new_password)
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                raise AccountError("USER_NOT_FOUND", "User not found.")
            if not _verify_secret(old_password, row["password_hash"]):
                raise AccountError("INVALID_CURRENT_PASSWORD", "Current password is incorrect.")
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (_hash_secret(new_password), to_iso_timestamp(), user_id),
            )

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
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                raise AccountError("USER_NOT_FOUND", "User not found.")
            if not _verify_secret(current_answer.strip(), row["security_answer_hash"]):
                raise AccountError("INVALID_SECURITY_ANSWER", "Security answer is incorrect.")
            conn.execute(
                """
                UPDATE users
                SET security_question = ?, security_answer_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (question, _hash_secret(answer), to_iso_timestamp(), user_id),
            )
            updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return _row_to_user(updated)

    def verify_security_answer(self, username: str, answer: str) -> bool:
        row = self.get_user_by_username(username)
        return bool(row and _verify_secret(answer.strip(), row["security_answer_hash"]))

    def reset_password(self, username: str, answer: str, new_password: str) -> None:
        validate_password(new_password)
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username.strip(),)).fetchone()
            if row is None or not _verify_secret(answer.strip(), row["security_answer_hash"]):
                raise AccountError("INVALID_SECURITY_ANSWER", "Security answer is incorrect.")
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (_hash_secret(new_password), to_iso_timestamp(), row["id"]),
            )
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (to_iso_timestamp(), row["id"]),
            )

    def delete_user(self, user_id: int, password: str) -> None:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                raise AccountError("USER_NOT_FOUND", "User not found.")
            if not _verify_secret(password, row["password_hash"]):
                raise AccountError("INVALID_CURRENT_PASSWORD", "Current password is incorrect.")
            conn.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (to_iso_timestamp(), user_id),
            )
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
