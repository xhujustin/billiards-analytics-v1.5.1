import os

import config
from auth.account_store import AccountStore
from storage.supabase_accounts import configured_supabase_account_store


def default_account_db_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")


def create_account_store(db_path: str | None = None, session_ttl_seconds: int | None = None):
    ttl = int(session_ttl_seconds or getattr(config, "AUTH_SESSION_TTL_SECONDS", 7 * 24 * 60 * 60))
    backend = os.getenv("ACCOUNT_STORE_BACKEND", "sqlite").strip().lower()
    if backend == "supabase":
        store = configured_supabase_account_store(session_ttl_seconds=ttl)
        if store is None:
            raise RuntimeError("ACCOUNT_STORE_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        return store
    if backend not in {"", "sqlite"}:
        raise RuntimeError(f"Unsupported ACCOUNT_STORE_BACKEND: {backend}")
    return AccountStore(db_path or default_account_db_path(), session_ttl_seconds=ttl)
