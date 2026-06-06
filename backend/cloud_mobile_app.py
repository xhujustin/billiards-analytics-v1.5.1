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
from storage.supabase_notifications import configured_supabase_notification_repository
from storage.supabase_posts import configured_supabase_post_repository
from storage.supabase_profiles import configured_supabase_profile_repository
from services.mobile_push_notifications import configured_mobile_push_notification_service


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
    supabase_rest = _supabase_rest_diagnostics(supabase_url, supabase_key)
    return {
        "deploy_mode": "cloud_mobile",
        "account_store_backend": os.getenv("ACCOUNT_STORE_BACKEND", "sqlite"),
        "supabase_configured": bool(supabase_url and supabase_key),
        "supabase_storage_bucket": os.getenv("SUPABASE_STORAGE_BUCKET", ""),
        "mobile_public_base_url": os.getenv("MOBILE_PUBLIC_BASE_URL", ""),
        "supabase_rest": supabase_rest,
        "supabase_rpc": _supabase_rpc_diagnostics(supabase_url, supabase_key),
        "notifications": supabase_rest.get("notifications", {}),
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


@app.get("/api/diagnostics/mobile-push-receipts")
async def mobile_push_receipts_diagnostics(limit: int = 10, check: bool = True) -> dict[str, Any]:
    repo = configured_supabase_notification_repository()
    if repo is None:
        return {"ok": False, "error": "Supabase notification repository is not configured."}
    try:
        events = repo.list_recent_sent_events(limit)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}

    receipt_results: list[dict[str, Any]] = []
    if check:
        service = configured_mobile_push_notification_service()
        if service is not None:
            for event in events:
                if event.get("expo_ticket_ids"):
                    try:
                        receipt_results.append(service.check_receipts_for_event(event))
                    except Exception as exc:
                        receipt_results.append({"event_id": event.get("id"), "status": "failed", "reason": str(exc)[:500]})
            try:
                events = repo.list_recent_sent_events(limit)
            except Exception:
                pass
    safe_events = [
        {
            "id": event.get("id"),
            "recipient_user_id": event.get("recipient_user_id"),
            "actor_user_id": event.get("actor_user_id"),
            "event_type": event.get("event_type"),
            "status": event.get("status"),
            "error": event.get("error"),
            "created_at": event.get("created_at"),
            "sent_at": event.get("sent_at"),
            "expo_ticket_count": len(event.get("expo_ticket_ids") or []),
            "expo_receipts": event.get("expo_receipts") or {},
            "receipt_checked_at": event.get("receipt_checked_at"),
        }
        for event in events
    ]
    return {"ok": True, "events": safe_events, "receipt_results": receipt_results}


def _supabase_rest_diagnostics(supabase_url: str, supabase_key: str) -> dict[str, Any]:
    if not supabase_url or not supabase_key:
        return {"ok": False, "error": "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing."}
    table_selects = {
        "mobile_users": "id",
        "mobile_auth_sessions": "id",
        "mobile_login_history": "id",
        "mobile_profiles": "user_id",
        "user_follows": "follower_user_id",
        "user_blocks": "blocker_user_id",
        "community_posts": "id",
        "community_post_reactions": "post_id",
        "community_comment_reactions": "comment_id",
        "community_comments": "id",
        "community_post_bookmarks": "post_id",
        "user_notification_settings": "user_id",
        "user_push_tokens": "id",
        "user_notification_events": "id",
    }
    column_checks = {
        "mobile_profiles.is_private": ("mobile_profiles", "is_private"),
        "mobile_users.is_deactivated": ("mobile_users", "is_deactivated"),
        "mobile_users.deactivated_at": ("mobile_users", "deactivated_at"),
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
    notifications = {
        "ok": all(results.get(table, {}).get("ok") for table in ("user_notification_settings", "user_push_tokens", "user_notification_events")),
        "expo_push_api": {
            "ok": True,
            "endpoint": "https://exp.host/--/api/v2/push/send",
            "auth_required": False,
        },
    }
    return {"ok": ok, "tables": results, "columns": columns, "notifications": notifications}


def _supabase_rpc_diagnostics(supabase_url: str, supabase_key: str) -> dict[str, Any]:
    if not supabase_url or not supabase_key:
        return {"ok": False, "error": "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing."}
    checks = {
        "mobile_hydrated_posts": {
            "viewer_user_id": 0,
            "post_ids": [],
        },
        "mobile_following_feed": {
            "viewer_user_id": 0,
            "page_limit": 1,
            "page_offset": 0,
        },
        "mobile_trending_feed": {
            "viewer_user_id": 0,
            "page_limit": 1,
            "page_offset": 0,
            "exclude_ids": [],
        },
        "mobile_user_posts": {
            "viewer_user_id": 0,
            "author_user_id": 0,
            "page_limit": 1,
            "page_offset": 0,
        },
        "mobile_toggle_post_like": {
            "viewer_user_id": 0,
            "post_id": 0,
        },
        "mobile_toggle_post_bookmark": {
            "viewer_user_id": 0,
            "post_id": 0,
        },
        "mobile_bookmarked_posts": {
            "viewer_user_id": 0,
            "page_limit": 1,
            "page_offset": 0,
        },
        "mobile_hydrated_comments": {
            "viewer_user_id": 0,
            "comment_ids": [],
        },
        "mobile_comments_for_post": {
            "viewer_user_id": 0,
            "target_post_id": 0,
        },
        "mobile_create_comment": {
            "viewer_user_id": 0,
            "target_post_id": 0,
            "comment_body": "diagnostics",
        },
        "mobile_toggle_comment_like": {
            "viewer_user_id": 0,
            "target_comment_id": 0,
        },
    }
    results: dict[str, Any] = {}
    ok = True
    for function_name, payload in checks.items():
        endpoint = f"{supabase_url}/rest/v1/rpc/{function_name}"
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with request.urlopen(req, timeout=8) as response:
                raw = response.read().decode("utf-8", errors="replace")
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            rows = json.loads(raw) if raw else []
            results[function_name] = {
                "ok": True,
                "status": 200,
                "ms": elapsed_ms,
                "rows": len(rows) if isinstance(rows, list) else 1,
            }
        except error.HTTPError as exc:
            ok = False
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            results[function_name] = {
                "ok": False,
                "status": exc.code,
                "ms": elapsed_ms,
                "error": exc.read().decode("utf-8", errors="replace")[:240],
            }
        except Exception as exc:
            ok = False
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            results[function_name] = {"ok": False, "ms": elapsed_ms, "error": str(exc)[:240]}
    return {"ok": ok, "functions": results}
