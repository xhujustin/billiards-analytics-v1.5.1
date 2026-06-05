import os
import json
import time
from typing import Any
from urllib import error, parse, request

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth_api import router as auth_router
from api.community_api import router as community_router
from api import mobile_api
from api.mobile_api import router as mobile_router
from storage.supabase_accounts import configured_supabase_account_store
from storage.supabase_follows import configured_supabase_follow_repository
from storage.supabase_posts import configured_supabase_post_repository
from storage.supabase_profiles import configured_supabase_profile_repository


APP_STARTED_AT = time.time()

app = FastAPI(title="CueVex Mobile Cloud API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(community_router)
app.include_router(mobile_router)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "cuevex-mobile-cloud",
        "uptime_sec": round(time.time() - APP_STARTED_AT, 3),
        "account_store_backend": os.getenv("ACCOUNT_STORE_BACKEND", "sqlite"),
        "supabase_configured": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
    }


@app.get("/api/diagnostics/cloud-mobile")
async def cloud_mobile_diagnostics() -> dict[str, Any]:
    supabase_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    return {
        "deploy_mode": "cloud_mobile",
        "account_store_backend": os.getenv("ACCOUNT_STORE_BACKEND", "sqlite"),
        "supabase_configured": bool(supabase_url and supabase_key),
        "supabase_storage_bucket": os.getenv("SUPABASE_STORAGE_BUCKET", ""),
        "mobile_public_base_url": os.getenv("MOBILE_PUBLIC_BASE_URL", ""),
        "supabase_rest": _supabase_rest_diagnostics(supabase_url, supabase_key),
    }


@app.get("/api/diagnostics/mobile-profile/{user_id}")
async def mobile_profile_diagnostics(user_id: int) -> dict[str, Any]:
    account_store = configured_supabase_account_store()
    if account_store is None:
        return {"ok": False, "error": "Supabase account store is not configured."}
    result: dict[str, Any] = {"ok": True, "user_id": user_id, "checks": {}}
    try:
        user = account_store.get_public_user_by_id(user_id)
        result["checks"]["user"] = {
            "ok": bool(user),
            "username": user.get("username") if user else "",
            "avatar_url": user.get("avatar_url") if user else "",
        }
    except Exception as exc:
        result["ok"] = False
        result["checks"]["user"] = {"ok": False, "error": str(exc)[:240]}
        user = None

    profile_repo = configured_supabase_profile_repository()
    try:
        profile = profile_repo.get_profile(user_id) if profile_repo else None
        result["checks"]["profile"] = {
            "ok": True,
            "exists": bool(profile),
            "avatar_url": profile.get("avatar_url") if profile else "",
            "display_name": profile.get("display_name") if profile else "",
            "is_private": profile.get("is_private") if profile else False,
        }
    except Exception as exc:
        result["ok"] = False
        result["checks"]["profile"] = {"ok": False, "error": str(exc)[:240]}

    follow_repo = configured_supabase_follow_repository()
    try:
        counts = follow_repo.follow_counts(user_id) if follow_repo else {"followers_count": 0, "following_count": 0}
        result["checks"]["follow_counts"] = {"ok": True, **counts}
    except Exception as exc:
        result["ok"] = False
        result["checks"]["follow_counts"] = {"ok": False, "error": str(exc)[:240]}

    post_repo = configured_supabase_post_repository()
    try:
        posts, total = post_repo.list_posts_for_user(user_id, limit=5, offset=0, viewer_user_id=user_id) if post_repo else ([], 0)
        result["checks"]["posts"] = {
            "ok": True,
            "total": total,
            "returned": len(posts),
            "sample": [
                {
                    "id": post.get("id"),
                    "user_id": post.get("user_id"),
                    "author_name": post.get("author_name"),
                    "author_avatar_url": post.get("author_avatar_url"),
                }
                for post in posts[:3]
            ],
        }
    except Exception as exc:
        result["ok"] = False
        result["checks"]["posts"] = {"ok": False, "error": str(exc)[:240]}

    if user:
        try:
            payload = mobile_api._mobile_profile_payload(user, user_id)
            result["checks"]["mobile_profile_payload"] = {
                "ok": True,
                "display_name": payload.get("display_name", ""),
                "avatar_url": payload.get("avatar_url", ""),
                "is_private": payload.get("is_private", False),
                "post_count": payload.get("post_count", 0),
                "followers_count": payload.get("followers_count", 0),
                "following_count": payload.get("following_count", 0),
            }
        except Exception as exc:
            result["ok"] = False
            result["checks"]["mobile_profile_payload"] = {"ok": False, "error": str(exc)[:240]}
    return result


def _supabase_rest_diagnostics(supabase_url: str, supabase_key: str) -> dict[str, Any]:
    if not supabase_url or not supabase_key:
        return {"ok": False, "error": "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing."}
    table_selects = {
        "mobile_users": "id",
        "mobile_auth_sessions": "id",
        "mobile_login_history": "id",
        "mobile_profiles": "user_id",
        "user_follows": "follower_user_id",
        "community_posts": "id",
        "community_post_reactions": "post_id",
        "community_comments": "id",
        "community_post_bookmarks": "post_id",
    }
    column_checks = {
        "mobile_profiles.is_private": ("mobile_profiles", "is_private"),
    }
    results: dict[str, Any] = {}
    ok = True
    for table, select_column in table_selects.items():
        params = parse.urlencode({"select": select_column, "limit": "1"})
        endpoint = f"{supabase_url}/rest/v1/{table}?{params}"
        req = request.Request(
            endpoint,
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=8) as response:
                raw = response.read().decode("utf-8", errors="replace")
            results[table] = {"ok": True, "status": 200, "rows": len(json.loads(raw) if raw else [])}
        except error.HTTPError as exc:
            ok = False
            results[table] = {
                "ok": False,
                "status": exc.code,
                "error": exc.read().decode("utf-8", errors="replace")[:240],
            }
        except Exception as exc:
            ok = False
            results[table] = {"ok": False, "error": str(exc)[:240]}
    columns: dict[str, Any] = {}
    for label, (table, column) in column_checks.items():
        params = parse.urlencode({"select": column, "limit": "1"})
        endpoint = f"{supabase_url}/rest/v1/{table}?{params}"
        req = request.Request(
            endpoint,
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=8) as response:
                response.read()
            columns[label] = {"ok": True, "status": 200}
        except error.HTTPError as exc:
            ok = False
            columns[label] = {
                "ok": False,
                "status": exc.code,
                "error": exc.read().decode("utf-8", errors="replace")[:240],
            }
        except Exception as exc:
            ok = False
            columns[label] = {"ok": False, "error": str(exc)[:240]}
    return {"ok": ok, "tables": results, "columns": columns}
