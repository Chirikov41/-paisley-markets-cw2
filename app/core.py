"""Shared Jinja2 environment and small response helpers."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .security import csrf_token, current_admin

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

STATUS_LABELS = {
    "submitted": "Submitted",
    "under_review": "Under review",
    "approved": "Approved",
    "rejected": "Not accepted",
    "withdrawn": "Withdrawn",
}

DAY_LABELS = {
    "weekend-1": "Fri 27 - Sun 29 Nov",
    "weekend-2": "Fri 4 - Sun 6 Dec",
}


def flash(request: Request, message: str, kind: str = "success") -> None:
    request.session.setdefault("flashes", []).append({"message": message, "kind": kind})


def pop_flashes(request: Request) -> list[dict]:
    return request.session.pop("flashes", [])


def render(request: Request, template: str, context: dict | None = None, status_code: int = 200):
    payload = {
        "request": request,
        "csrf_token": csrf_token(request),
        "admin": current_admin(request),
        "flashes": pop_flashes(request),
        "status_labels": STATUS_LABELS,
        "day_labels": DAY_LABELS,
    }
    payload.update(context or {})
    return templates.TemplateResponse(request, template, payload, status_code=status_code)


def safe_redirect(target: str | None, fallback: str = "/") -> RedirectResponse:
    """Only allow same-site relative redirects (prevents open redirects)."""
    if not target:
        return RedirectResponse(fallback, status_code=303)
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/"):
        return RedirectResponse(fallback, status_code=303)
    return RedirectResponse(target, status_code=303)
