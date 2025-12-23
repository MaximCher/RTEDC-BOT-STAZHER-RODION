from __future__ import annotations

import secrets
from typing import Set

from fastapi import HTTPException, Request

from src.config import settings


SESSION_COOKIE = "admin_session"
_active_sessions: Set[str] = set()


def create_session() -> str:
    session_id = secrets.token_urlsafe(32)
    _active_sessions.add(session_id)
    return session_id


def destroy_session(session_id: str) -> None:
    _active_sessions.discard(session_id)


def require_auth(request: Request) -> None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id or session_id not in _active_sessions:
        raise HTTPException(status_code=401, detail="Authentication required")


def validate_password(password: str) -> None:
    if not password or password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Invalid password")
