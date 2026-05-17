import os
import sys
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth.account_store import AccountStore
from database.database import Database


db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
account_store = AccountStore(db_path)
db = Database(db_path)
router = APIRouter()

VALID_PREVIEW_TYPES = {"pool-table", "pool-table-alt", "pose-analysis", "stats"}


class CommunityPostRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=80)
    body: str = Field(..., min_length=1, max_length=800)
    preview_type: str = "pool-table"
    recording_id: Optional[str] = None


class CommunityCommentRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=500)


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization[7:].strip()


def _current_user(authorization: str | None) -> dict:
    token = _extract_token(authorization)
    user = account_store.authenticate_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    return user


def _optional_user(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    try:
        return _current_user(authorization)
    except HTTPException:
        return None


def _normalize_preview_type(value: str) -> str:
    if value not in VALID_PREVIEW_TYPES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PREVIEW_TYPE", "message": "Invalid preview type"})
    return value


def _tone_for_user(user_id: int) -> str:
    tones = ["aqua", "amber", "green", "rose", "indigo", "blue"]
    return tones[user_id % len(tones)]


@router.get("/api/community/posts")
async def get_community_posts(
    authorization: Annotated[str | None, Header()] = None,
    tab: str = Query("all", pattern="^(all|explore|following)$"),
    sort: str = Query("latest", pattern="^(latest|popular|comments)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    user = _optional_user(authorization)
    try:
        posts, total = db.get_community_posts(
            tab=tab,
            sort=sort,
            limit=limit,
            offset=offset,
            viewer_user_id=int(user["id"]) if user else None,
        )
        return {"posts": posts, "total": total, "limit": limit, "offset": offset}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": str(exc)}) from exc


@router.post("/api/community/posts")
async def create_community_post(
    request: Annotated[CommunityPostRequest, Body(...)],
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    title = request.title.strip()
    body = request.body.strip()
    if not title or not body:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "Title and body are required"})

    post = db.insert_community_post(
        {
            "user_id": int(user["id"]),
            "author_name": user["username"],
            "badge": "玩家",
            "title": title,
            "body": body,
            "preview_type": _normalize_preview_type(request.preview_type),
            "recording_id": request.recording_id,
            "tone": _tone_for_user(int(user["id"])),
        }
    )
    return JSONResponse(post, status_code=201)


@router.post("/api/community/posts/{post_id}/like")
async def toggle_community_like(post_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    try:
        return db.toggle_community_like(post_id, int(user["id"]))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.post("/api/community/posts/{post_id}/bookmark")
async def toggle_community_bookmark(post_id: int, authorization: Annotated[str | None, Header()] = None):
    user = _current_user(authorization)
    try:
        return db.toggle_community_bookmark(post_id, int(user["id"]))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.get("/api/community/posts/{post_id}/comments")
async def get_community_comments(post_id: int):
    try:
        comments = db.get_community_comments(post_id)
        return {"comments": comments, "total": len(comments)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc


@router.post("/api/community/posts/{post_id}/comments")
async def create_community_comment(
    post_id: int,
    request: Annotated[CommunityCommentRequest, Body(...)],
    authorization: Annotated[str | None, Header()] = None,
):
    user = _current_user(authorization)
    body = request.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ARGUMENT", "message": "Comment body is required"})

    try:
        comment = db.insert_community_comment(post_id, int(user["id"]), user["username"], body)
        post = db.get_community_post(post_id, int(user["id"]))
        return JSONResponse({"comment": comment, "post": post}, status_code=201)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "POST_NOT_FOUND", "message": "Post not found"}) from exc
