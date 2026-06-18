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

from storage.supabase_analytics import configured_supabase_analytics_repository


DEFAULT_DB_PATH = ROOT / "backend" / "data" / "recordings.db"
DEFAULT_ENV_PATH = ROOT / "mobile-remote.env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


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


def normalize_event(row: dict[str, Any]) -> dict[str, Any]:
    event = dict(row)
    event["local_event_id"] = row.get("id")
    return event


def migrate(db_path: Path, apply: bool, env_path: Path) -> int:
    if not db_path.exists():
        print(f"ERROR SQLite database not found: {db_path}")
        return 1

    load_env_file(env_path)
    with connect_sqlite(db_path) as conn:
        recordings = fetch_rows(conn, "recordings")
        events = fetch_rows(conn, "events")
        shot_events = fetch_rows(conn, "shot_events")
        practice_stats = fetch_rows(conn, "practice_stats")

    print(f"SQLite: {db_path}")
    print(f"Recordings: {len(recordings)}")
    print(f"Events: {len(events)}")
    print(f"Shot events: {len(shot_events)}")
    print(f"Practice stats: {len(practice_stats)}")

    if not apply:
        print("Dry-run only. Re-run with --apply to write to Supabase.")
        return 0

    repo = configured_supabase_analytics_repository()
    if repo is None:
        print("ERROR SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
        return 1

    imported = {
        "recordings": 0,
        "events": 0,
        "shot_events": 0,
        "practice_stats": 0,
    }
    for row in recordings:
        repo.upsert_recording(row)
        imported["recordings"] += 1
    for row in events:
        repo.upsert_event(normalize_event(row))
        imported["events"] += 1
    for row in shot_events:
        repo.upsert_shot_event(row)
        imported["shot_events"] += 1
    for row in practice_stats:
        repo.upsert_practice_stats(row)
        imported["practice_stats"] += 1

    print("Supabase analytics import complete:")
    for key, value in imported.items():
        print(f"  {key}={value}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate CueVex SQLite analytics data to Supabase.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to backend SQLite recordings.db.")
    parser.add_argument("--env", default=str(DEFAULT_ENV_PATH), help="Path to env file containing Supabase credentials.")
    parser.add_argument("--apply", action="store_true", help="Write data to Supabase. Omit for dry-run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return migrate(Path(args.db).resolve(), bool(args.apply), Path(args.env).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
