"""Trader application form, confirmation page and public status lookup."""

from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from ..content import MARKET, PREFERRED_DAYS, STALL_TYPES
from ..core import render
from ..db import get_db, log_event, utcnow
from ..security import check_csrf

router = APIRouter()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[0-9+()\s-]{7,30}$")

FIELD_LIMITS = {
    "business_name": (2, 80),
    "contact_name": (2, 80),
    "product_summary": (40, 700),
}


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _validate(form, categories: list[sqlite3.Row]) -> tuple[dict, dict[str, str]]:
    values = {
        "business_name": _clean(form.get("business_name")),
        "contact_name": _clean(form.get("contact_name")),
        "email": _clean(form.get("email")).lower(),
        "phone": _clean(form.get("phone")),
        "category_id": _clean(form.get("category_id")),
        "product_summary": _clean(form.get("product_summary")),
        "stall_type": _clean(form.get("stall_type")) or "standard",
        "preferred_days": form.getlist("preferred_days"),
        "power_required": "yes" if form.get("power_required") else "",
        "consent": "yes" if form.get("consent") else "",
    }

    errors: dict[str, str] = {}
    for field, (low, high) in FIELD_LIMITS.items():
        value = values[field]
        if not value:
            errors[field] = "This field is required."
        elif len(value) < low:
            errors[field] = f"Please use at least {low} characters."
        elif len(value) > high:
            errors[field] = f"Please keep this under {high} characters."

    if values["email"] and not EMAIL_RE.match(values["email"]):
        errors["email"] = "Enter a valid email address, for example name@example.com."

    if values["phone"] and not PHONE_RE.match(values["phone"]):
        errors["phone"] = "Use digits, spaces, brackets, + or - only."

    valid_ids = {str(row["id"]) for row in categories}
    if values["category_id"] not in valid_ids:
        errors["category_id"] = "Choose the category that fits your stall."

    valid_stalls = {slug for slug, _, _ in STALL_TYPES}
    if values["stall_type"] not in valid_stalls:
        errors["stall_type"] = "Choose a pitch type."

    valid_days = {slug for slug, _ in PREFERRED_DAYS}
    if not values["preferred_days"]:
        errors["preferred_days"] = "Select at least one weekend."
    elif not set(values["preferred_days"]) <= valid_days:
        errors["preferred_days"] = "Choose from the available weekends."

    if not values["consent"]:
        errors["consent"] = "We need your consent before we can store the application."

    return values, errors


def _form_context(db: sqlite3.Connection, values: dict, errors: dict) -> dict:
    return {
        "market": MARKET,
        "categories": db.execute("SELECT * FROM categories ORDER BY name").fetchall(),
        "stall_types": STALL_TYPES,
        "preferred_days": PREFERRED_DAYS,
        "values": values,
        "errors": errors,
    }


@router.get("/apply")
def apply_page(request: Request, db: sqlite3.Connection = Depends(get_db)):
    return render(request, "apply.html", _form_context(db, {}, {}))


@router.post("/apply")
async def submit_application(request: Request, db: sqlite3.Connection = Depends(get_db)):
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))

    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    values, errors = _validate(form, categories)

    if not errors:
        duplicate = db.execute(
            """SELECT reference FROM applications
                WHERE lower(email) = ? AND lower(business_name) = ?
                  AND status NOT IN ('rejected', 'withdrawn')""",
            (values["email"], values["business_name"].lower()),
        ).fetchone()
        if duplicate:
            errors["business_name"] = (
                f"An application for this business is already open ({duplicate['reference']}). "
                "Use the status page to check its progress."
            )

    if errors:
        return render(request, "apply.html", _form_context(db, values, errors), status_code=422)

    now = utcnow()
    token = f"pending-{secrets.token_hex(8)}"
    cursor = db.execute(
        """INSERT INTO applications
               (reference, business_name, contact_name, email, phone, category_id,
                product_summary, preferred_days, stall_type, power_required, status,
                consent_given, consent_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', 1, ?, ?, ?)""",
        (
            token,
            values["business_name"],
            values["contact_name"],
            values["email"],
            values["phone"] or None,
            int(values["category_id"]),
            values["product_summary"],
            ",".join(values["preferred_days"]),
            values["stall_type"],
            1 if values["power_required"] else 0,
            now,
            now,
            now,
        ),
    )
    reference = f"PCM-{MARKET['year']}-{cursor.lastrowid:04d}"
    db.execute("UPDATE applications SET reference = ? WHERE id = ?", (reference, cursor.lastrowid))
    log_event(db, values["email"], "application.created", "application", cursor.lastrowid,
              f"reference={reference}")
    db.commit()

    return RedirectResponse(f"/apply/success?ref={reference}", status_code=303)


@router.get("/apply/success")
def apply_success(request: Request, ref: str = "", db: sqlite3.Connection = Depends(get_db)):
    application = db.execute(
        "SELECT * FROM applications WHERE reference = ?", (ref,)
    ).fetchone()
    return render(request, "apply_success.html", {"market": MARKET, "application": application})


@router.get("/status")
def status_page(request: Request):
    return render(request, "status.html", {"market": MARKET, "errors": {}, "values": {}})


@router.post("/status")
def status_lookup(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    reference: str = Form(""),
    email: str = Form(""),
    csrf: str = Form("", alias="csrf_token"),
):
    check_csrf(request, csrf)
    values = {"reference": reference.strip().upper(), "email": email.strip().lower()}
    errors: dict[str, str] = {}
    if not values["reference"]:
        errors["reference"] = "Enter the reference from your confirmation email."
    if not EMAIL_RE.match(values["email"]):
        errors["email"] = "Enter the email address used on the application."

    application = None
    if not errors:
        application = db.execute(
            """SELECT a.*, c.name AS category_name
                 FROM applications a JOIN categories c ON c.id = a.category_id
                WHERE a.reference = ? AND lower(a.email) = ?""",
            (values["reference"], values["email"]),
        ).fetchone()
        if application is None:
            errors["reference"] = (
                "We could not match that reference and email. Check both values and try again."
            )

    if errors:
        return render(request, "status.html",
                      {"market": MARKET, "errors": errors, "values": values}, status_code=422)

    return render(
        request,
        "status.html",
        {
            "market": MARKET,
            "errors": {},
            "values": values,
            "application": application,
            "submitted_on": datetime.fromisoformat(application["created_at"]).strftime("%d %B %Y"),
        },
    )
