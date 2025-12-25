from __future__ import annotations

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from src.config import settings  # type: ignore
from src.database import close_db, init_db
from src.logger import setup_logging
from src.utils.rate_limit import FixedWindowLimiter
from src.web.api import register_api
from src.web.health import check_bot_heartbeat, check_db, check_openai

# mypy: ignore-errors
# pyright: reportMissingImports=false, reportMissingTypeStubs=false


def create_app() -> FastAPI:
    app = FastAPI(title="SRVT Admin Panel", version="0.1.0")
    limiter = FixedWindowLimiter(
        limit=60, window_sec=60
    )  # 60 req/min per IP per path

    templates = Jinja2Templates(directory="src/web/templates")
    app.mount(
        "/static",
        StaticFiles(directory="src/web/static"),
        name="static",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        # Avoid noisy 404s in browsers; we don't ship a favicon yet.
        return Response(status_code=204)

    # Cookie-signed sessions for admin login (no in-memory session storage).
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.web_session_secret,
        session_cookie="admin_session",
        max_age=86400,  # 1 day
        same_site="lax",
        https_only=not settings.debug_mode,
    )

    @app.get("/health")
    async def health(checkOpenAI: bool = False) -> dict:  # noqa: N803
        # DB + bot heartbeat are always checked.
        # OpenAI check is optional to avoid extra network calls.
        from src.database import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as session:
            db_ok = await check_db(session)
            bot = await check_bot_heartbeat(session)

        openai_payload = {"configured": bool(settings.openai_api_key), "checked": bool(checkOpenAI), "ok": None}
        if checkOpenAI:
            openai_payload = await check_openai()
            openai_payload["checked"] = True

        overall = bool(db_ok and bot.get("ok"))
        return {
            "ok": overall,
            "db": {"ok": db_ok},
            "bot": bot,
            "openai": openai_payload,
        }

    register_api(app)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        path = request.url.path
        # Only protect API endpoints (UI assets are static)
        if path.startswith("/api/"):
            ip = request.client.host if request.client else "unknown"
            key = f"{ip}:{path}"
            if not limiter.allow(key):
                return JSONResponse(
                    {"detail": "Rate limit exceeded"},
                    status_code=429,
                )
        return await call_next(request)

    @app.on_event("startup")
    async def _startup() -> None:
        await init_db()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await close_db()

    return app


app = create_app()


if __name__ == "__main__":
    setup_logging(settings.log_level, settings.debug_mode)
    uvicorn.run(
        "src.web_server:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=False,
    )
