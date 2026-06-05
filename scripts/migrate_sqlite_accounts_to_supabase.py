import argparse
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from storage.supabase_accounts import configured_supabase_account_store


DEFAULT_DB_PATH = ROOT / "backend" / "data" / "recordings.db"


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY id ASC").fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


def detect_username_conflicts(users: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, str] = {}
    conflicts: list[str] = []
    for user in users:
        username = str(user.get("username") or "")
        key = username.lower()
        if key in seen and seen[key] != username:
            conflicts.append(username)
        else:
            seen[key] = username
    return conflicts


def migrate(db_path: Path, apply: bool) -> int:
    if not db_path.exists():
        print(f"ERROR SQLite database not found: {db_path}")
        return 1
    with connect_sqlite(db_path) as conn:
        users = fetch_rows(conn, "users")
        login_history = fetch_rows(conn, "login_history")
        friendships = fetch_rows(conn, "friendships")

    conflicts = detect_username_conflicts(users)
    print(f"SQLite: {db_path}")
    print(f"Users: {len(users)}")
    print(f"Login history: {len(login_history)}")
    print(f"Friendships: {len(friendships)}")
    print("Auth sessions: skipped")
    if conflicts:
        print("Username conflicts in SQLite:")
        for username in conflicts:
            print(f"  - {username}")
        return 1
    if not apply:
        print("Dry-run only. Re-run with --apply to write to Supabase.")
        return 0

    store = configured_supabase_account_store()
    if store is None:
        print("ERROR SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
        return 1

    imported_users = 0
    imported_history = 0
    imported_friendships = 0
    for user in users:
        store.import_user(user)
        imported_users += 1
    for row in login_history:
        store.import_login_history(row)
        imported_history += 1
    for row in friendships:
        store.import_friendship(row)
        imported_friendships += 1

    print("Supabase import complete:")
    print(f"  users={imported_users}")
    print(f"  login_history={imported_history}")
    print(f"  friendships={imported_friendships}")
    print("  auth_sessions=0")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate CueVex SQLite account data to Supabase.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to backend SQLite recordings.db.")
    parser.add_argument("--apply", action="store_true", help="Write data to Supabase. Omit for dry-run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return migrate(Path(args.db).resolve(), bool(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
