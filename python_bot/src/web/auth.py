from __future__ import annotations

from fastapi import HTTPException, Request

from src.config import settings


SESSION_COOKIE = "admin_session"  # cookie name used by SessionMiddleware
SESSION_KEY = "admin_authenticated"

def require_auth(request: Request) -> None:
    # Session is backed by signed cookies (Starlette SessionMiddleware).
    if not request.session.get(SESSION_KEY):
        raise HTTPException(status_code=401, detail="Authentication required")


def validate_password(password: str) -> None:
    if not password or password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid password")
