"""Application factory for the Paisley Christmas Markets proof of concept."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .db import init_db
from .routes import admin, apply, public

LOG = logging.getLogger("paisley")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    LOG.info("database ready at %s", os.getenv("DATABASE_PATH", "data/market.db"))
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Paisley Christmas Markets",
        description="Proof of concept for COMP10020 Coursework 2.",
        version="1.0.0",
        lifespan=lifespan,
    )

    secret = os.getenv("SECRET_KEY", "dev-only-change-me")
    if secret == "dev-only-change-me":
        LOG.warning("SECRET_KEY is not set - sessions are signed with the development key")
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        same_site="lax",
        https_only=os.getenv("SESSION_HTTPS_ONLY", "0") == "1",
    )

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(public.router)
    app.include_router(apply.router)
    app.include_router(admin.router)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    @app.exception_handler(404)
    async def not_found(request: Request, exc):  # pragma: no cover - template path
        from .content import MARKET
        from .core import render

        return render(request, "404.html", {"market": MARKET}, status_code=404)

    return app


app = create_app()
