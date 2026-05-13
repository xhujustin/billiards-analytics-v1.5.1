import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from auth.account_store import AccountError, AccountStore, validate_password, validate_username


def make_store(tmp_path: Path) -> AccountStore:
    return AccountStore(str(tmp_path / "accounts.db"), session_ttl_seconds=60)


@pytest.mark.parametrize(
    "password",
    [
        "A1b2C3d4E",
        "OnlyLetters",
        "1234567890",
        "Password123中文",
        "Password_123",
        "Password 123",
        "Password!123",
    ],
)
def test_password_policy_rejects_invalid_values(password: str) -> None:
    with pytest.raises(AccountError):
        validate_password(password)


def test_password_policy_accepts_letters_and_numbers_only() -> None:
    validate_password("Password123")


def test_username_policy_allows_underscore() -> None:
    assert validate_username("Lucian_039") == "Lucian_039"


@pytest.mark.parametrize("username", ["中文帳號", "Player-001", "Player 001", "ab"])
def test_username_policy_rejects_invalid_values(username: str) -> None:
    with pytest.raises(AccountError):
        validate_username(username)


def test_register_login_me_and_logout_flow(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    user = store.create_user("Player001", "Password123", "Question?", "Answer")

    session = store.login("Player001", "Password123", "Chrome / Windows")
    assert session["user"]["username"] == user["username"]
    assert store.authenticate_token(session["token"])["username"] == "Player001"

    history = store.get_login_history(user["id"])
    assert history[0]["status"] == "success"

    store.revoke_token(session["token"])
    assert store.authenticate_token(session["token"]) is None


def test_duplicate_username_and_failed_login_history(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    user = store.create_user("Player001", "Password123", "Question?", "Answer")

    with pytest.raises(AccountError) as duplicate:
        store.create_user("player001", "Password123", "Question?", "Answer")
    assert duplicate.value.code == "USERNAME_TAKEN"

    with pytest.raises(AccountError) as login_error:
        store.login("Player001", "Wrongpass123", "Chrome / Windows")
    assert login_error.value.code == "INVALID_LOGIN"

    history = store.get_login_history(user["id"])
    assert history[0]["status"] == "failed"


def test_update_password_and_reset_password_flow(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.create_user("Player001", "Password123", "Question?", "Answer")

    session = store.login("Player001", "Password123")
    user_id = session["user"]["id"]
    store.change_password(user_id, "Password123", "Newpass1234")

    with pytest.raises(AccountError):
        store.login("Player001", "Password123")
    assert store.login("Player001", "Newpass1234")["user"]["username"] == "Player001"

    assert store.verify_security_answer("Player001", "Answer")
    store.reset_password("Player001", "Answer", "Resetpass123")
    assert store.login("Player001", "Resetpass123")["user"]["username"] == "Player001"


def test_update_profile_security_question_and_delete_account(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    user = store.create_user("Player001", "Password123", "Question?", "Answer")

    updated_user = store.update_username(user["id"], "Player002")
    assert updated_user["username"] == "Player002"

    updated_security = store.update_security_question(user["id"], "Answer", "New question?", "New answer")
    assert updated_security["security_question"] == "New question?"
    assert store.verify_security_answer("Player002", "New answer")

    session = store.login("Player002", "Password123")
    store.delete_user(user["id"], "Password123")
    assert store.authenticate_token(session["token"]) is None
    assert store.get_public_user_by_username("Player002") is None
