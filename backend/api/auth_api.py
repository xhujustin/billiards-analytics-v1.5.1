import os
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

import config
from auth.account_store import AccountError, AccountStore
from auth.account_store_factory import create_account_store
from storage.supabase_accounts import SupabaseAccountError


project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
default_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "recordings.db")
account_store = create_account_store(default_db_path, int(getattr(config, "AUTH_SESSION_TTL_SECONDS", 7 * 24 * 60 * 60)))


class RegisterRequest(BaseModel):
    username: str
    password: str
    security_question: str
    security_answer: str
    device: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str
    device: str = ""


class UpdateProfileRequest(BaseModel):
    username: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UpdateSecurityQuestionRequest(BaseModel):
    current_answer: str
    security_question: str
    security_answer: str


class PasswordResetVerifyRequest(BaseModel):
    username: str
    security_answer: str


class PasswordResetCompleteRequest(BaseModel):
    username: str
    security_answer: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    password: str


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization[7:].strip()


def _error_response(error: AccountError) -> HTTPException:
    status_code = 400
    if error.code == "INVALID_LOGIN":
        status_code = 401
    if error.code == "USER_NOT_FOUND":
        status_code = 404
    if error.code == "USERNAME_TAKEN":
        status_code = 409
    return HTTPException(status_code=status_code, detail={"code": error.code, "message": error.message})


def _storage_error_response(error: SupabaseAccountError) -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "code": "ACCOUNT_STORE_ERROR",
            "message": str(error),
        },
    )


def build_auth_router(store: AccountStore = account_store) -> APIRouter:
    router = APIRouter()

    async def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
        token = _extract_token(authorization)
        user = store.authenticate_token(token)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
        return {**user, "token": token}

    @router.post("/api/auth/register")
    async def register(request: Annotated[RegisterRequest, Body(...)]):
        try:
            user = store.create_user(
                request.username,
                request.password,
                request.security_question,
                request.security_answer,
            )
            store.record_login(int(user["id"]), user["username"], "success", request.device)
            return store.create_session(int(user["id"]), user)
        except AccountError as exc:
            raise _error_response(exc) from exc
        except SupabaseAccountError as exc:
            raise _storage_error_response(exc) from exc

    @router.post("/api/auth/login")
    async def login(request: Annotated[LoginRequest, Body(...)]):
        try:
            return store.login(request.username, request.password, request.device)
        except AccountError as exc:
            raise _error_response(exc) from exc
        except SupabaseAccountError as exc:
            raise _storage_error_response(exc) from exc

    @router.post("/api/auth/logout")
    async def logout(authorization: Annotated[str | None, Header()] = None):
        token = _extract_token(authorization)
        store.revoke_token(token)
        return {"status": "logged_out"}

    @router.get("/api/auth/me")
    async def me(user: Annotated[dict, Depends(current_user)]):
        login_history = store.get_login_history(int(user["id"]), limit=10)
        return {
            "user": {key: value for key, value in user.items() if key != "token"},
            "login_history": login_history,
        }

    @router.patch("/api/auth/me")
    async def update_me(
        request: Annotated[UpdateProfileRequest, Body(...)],
        user: Annotated[dict, Depends(current_user)],
    ):
        try:
            updated = store.update_username(int(user["id"]), request.username)
            return {"user": updated}
        except AccountError as exc:
            raise _error_response(exc) from exc

    @router.patch("/api/auth/password")
    async def change_password(
        request: Annotated[ChangePasswordRequest, Body(...)],
        user: Annotated[dict, Depends(current_user)],
    ):
        try:
            store.change_password(int(user["id"]), request.old_password, request.new_password)
            return {"status": "password_updated"}
        except AccountError as exc:
            raise _error_response(exc) from exc

    @router.patch("/api/auth/security-question")
    async def update_security_question(
        request: Annotated[UpdateSecurityQuestionRequest, Body(...)],
        user: Annotated[dict, Depends(current_user)],
    ):
        try:
            updated = store.update_security_question(
                int(user["id"]),
                request.current_answer,
                request.security_question,
                request.security_answer,
            )
            return {"user": updated}
        except AccountError as exc:
            raise _error_response(exc) from exc

    @router.get("/api/auth/password-reset/question")
    async def password_reset_question(username: Annotated[str, Query(...)]):
        user = store.get_public_user_by_username(username)
        if user is None:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "User not found."})
        return {"username": user["username"], "security_question": user["security_question"]}

    @router.post("/api/auth/password-reset/verify")
    async def password_reset_verify(request: Annotated[PasswordResetVerifyRequest, Body(...)]):
        if not store.verify_security_answer(request.username, request.security_answer):
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_SECURITY_ANSWER", "message": "Security answer is incorrect."},
            )
        return {"verified": True}

    @router.post("/api/auth/password-reset/complete")
    async def password_reset_complete(request: Annotated[PasswordResetCompleteRequest, Body(...)]):
        try:
            store.reset_password(request.username, request.security_answer, request.new_password)
            return {"status": "password_updated"}
        except AccountError as exc:
            raise _error_response(exc) from exc

    @router.delete("/api/auth/me")
    async def delete_me(
        request: Annotated[DeleteAccountRequest, Body(...)],
        user: Annotated[dict, Depends(current_user)],
    ):
        try:
            store.delete_user(int(user["id"]), request.password)
            return {"status": "deleted"}
        except AccountError as exc:
            raise _error_response(exc) from exc

    return router


router = build_auth_router(account_store)
