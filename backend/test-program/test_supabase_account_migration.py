import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from auth.account_store import AccountStore
from auth.account_store_factory import create_account_store
from scripts.migrate_sqlite_accounts_to_supabase import migrate


def test_account_store_factory_defaults_to_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACCOUNT_STORE_BACKEND", raising=False)
    store = create_account_store(str(tmp_path / "accounts.db"), session_ttl_seconds=60)

    user = store.create_user("Player001", "Password123", "Question?", "Answer")

    assert user["username"] == "Player001"


def test_account_store_factory_requires_supabase_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCOUNT_STORE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        create_account_store("unused.db", session_ttl_seconds=60)


def test_account_migration_dry_run_does_not_require_supabase(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "accounts.db"
    store = AccountStore(str(db_path), session_ttl_seconds=60)
    player_a = store.create_user("PlayerA", "Password123", "Question?", "Answer")
    player_b = store.create_user("PlayerB", "Password123", "Question?", "Answer")
    store.login("PlayerA", "Password123", "Test device")
    invite = store.create_friend_invite(player_a["id"])
    store.accept_friend_invite(player_b["id"], invite["token"])

    exit_code = migrate(db_path, apply=False)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Users: 2" in output
    assert "Friendships: 1" in output
    assert "Dry-run only" in output
