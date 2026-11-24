"""Administrator area: sign in, review applications, export, audit trail."""

from __future__ import annotations

import csv
import io
import sqlite3

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from ..content import MARKET
from ..core import flash, render
from ..db import get_db, log_event, utcnow
from ..security import check_csrf, current_admin, verify_password

router = APIRouter(prefix="/admin")

STATUS_FILTERS = [
    ("all", "All"),
    ("submitted", "Submitted"),
    ("under_review", "Under review"),
    ("approved", "Approved"),
    ("rejected", "Not accepted"),
]


def guard(request: Request):
    if current_admin(request) is None:
        flash(request, "Please sign in to open the market office.", "error")
        return RedirectResponse("/admin/login", status_code=303)
    return None


@router.get("/login")
def login_page(request: Request):
    if current_admin(request) is not None:
        return RedirectResponse("/admin", status_code=303)
    return render(request, "admin/login.html", {"market": MARKET})


@router.post("/login")
def login(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    username: str = Form(""),
    password: str = Form(""),
    csrf: str = Form("", alias="csrf_token"),
):
    check_csrf(request, csrf)
    attempts = request.session.get("login_attempts", 0)
    if attempts >= 8:
        flash(request, "Too many failed attempts. Close the browser and try again.", "error")
        return RedirectResponse("/admin/login", status_code=303)

    admin = db.execute("SELECT * FROM admins WHERE username = ?", (username.strip(),)).fetchone()
    if admin is None or not verify_password(password, admin["password_hash"]):
        request.session["login_attempts"] = attempts + 1
        log_event(db, username.strip() or "unknown", "admin.login_failed", "admin", None,
                  request.client.host if request.client else "unknown")
        db.commit()
        flash(request, "That username and password did not match.", "error")
        return RedirectResponse("/admin/login", status_code=303)

    request.session["login_attempts"] = 0
    request.session["admin_id"] = admin["id"]
    request.session["admin_username"] = admin["username"]
    log_event(db, admin["username"], "admin.login", "admin", admin["id"])
    db.commit()
    flash(request, f"Signed in as {admin['display_name']}.")
    return RedirectResponse("/admin", status_code=303)


@router.post("/logout")
def logout(request: Request, csrf: str = Form("", alias="csrf_token")):
    check_csrf(request, csrf)
    username = request.session.get("admin_username")
    request.session.pop("admin_id", None)
    request.session.pop("admin_username", None)
    if username:
        flash(request, "Signed out. The office is locked.", "info")
    return RedirectResponse("/", status_code=303)


@router.get("")
@router.get("/")
def dashboard(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    status: str = "all",
    q: str = "",
):
    if (redirect := guard(request)):
        return redirect

    where, params = "1 = 1", []
    if status in {"submitted", "under_review", "approved", "rejected", "withdrawn"}:
        where += " AND a.status = ?"
        params.append(status)
    if q.strip():
        where += " AND (a.business_name LIKE ? OR a.reference LIKE ? OR a.contact_name LIKE ?)"
        term = f"%{q.strip()}%"
        params.extend([term, term, term])

    applications = db.execute(
        f"""SELECT a.*, c.name AS category_name
              FROM applications a JOIN categories c ON c.id = a.category_id
             WHERE {where}
             ORDER BY a.created_at DESC""",
        params,
    ).fetchall()

    counts = {
        row["status"]: row["total"]
        for row in db.execute(
            "SELECT status, COUNT(*) AS total FROM applications GROUP BY status"
        ).fetchall()
    }
    return render(
        request,
        "admin/dashboard.html",
        {
            "market": MARKET,
            "applications": applications,
            "counts": counts,
            "total": sum(counts.values()),
            "active_status": status,
            "query": q,
            "status_filters": STATUS_FILTERS,
            "pending": counts.get("submitted", 0) + counts.get("under_review", 0),
        },
    )


@router.get("/applications/{application_id}")
def application_detail(
    application_id: int,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
):
    if (redirect := guard(request)):
        return redirect
    application = db.execute(
        """SELECT a.*, c.name AS category_name
             FROM applications a JOIN categories c ON c.id = a.category_id
            WHERE a.id = ?""",
        (application_id,),
    ).fetchone()
    if application is None:
        return render(request, "404.html", {"market": MARKET}, status_code=404)

    history = db.execute(
        """SELECT * FROM audit_log WHERE entity = 'application' AND entity_id = ?
            ORDER BY created_at DESC""",
        (application_id,),
    ).fetchall()
    return render(
        request,
        "admin/application.html",
        {"market": MARKET, "application": application, "history": history},
    )


@router.post("/applications/{application_id}/decision")
def decide(
    application_id: int,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    decision: str = Form(""),
    note: str = Form(""),
    csrf: str = Form("", alias="csrf_token"),
):
    if (redirect := guard(request)):
        return redirect
    check_csrf(request, csrf)

    application = db.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if application is None:
        return render(request, "404.html", {"market": MARKET}, status_code=404)

    if decision not in {"approved", "rejected", "under_review"}:
        flash(request, "Choose approve, reject or mark as under review.", "error")
        return RedirectResponse(f"/admin/applications/{application_id}", status_code=303)

    if decision == "rejected" and len(note.strip()) < 10:
        flash(request, "Please give the trader a short reason before rejecting.", "error")
        return RedirectResponse(f"/admin/applications/{application_id}", status_code=303)

    actor = request.session.get("admin_username", "admin")
    db.execute(
        "UPDATE applications SET status = ?, reviewer_note = ?, updated_at = ? WHERE id = ?",
        (decision, note.strip() or None, utcnow(), application_id),
    )
    log_event(db, actor, f"application.{decision}", "application", application_id,
              f"{application['reference']} {decision}")
    db.commit()
    flash(request, f"{application['reference']} marked {decision.replace('_', ' ')}.")
    return RedirectResponse(f"/admin/applications/{application_id}", status_code=303)


@router.post("/applications/{application_id}/delete")
def erase(
    application_id: int,
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    confirm: str = Form(""),
    csrf: str = Form("", alias="csrf_token"),
):
    """GDPR article 17 erasure request, performed by the market office."""
    if (redirect := guard(request)):
        return redirect
    check_csrf(request, csrf)

    application = db.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if application is None:
        return render(request, "404.html", {"market": MARKET}, status_code=404)

    if confirm.strip().upper() != "DELETE":
        flash(request, "Type DELETE to confirm permanent erasure.", "error")
        return RedirectResponse(f"/admin/applications/{application_id}", status_code=303)

    actor = request.session.get("admin_username", "admin")
    db.execute("DELETE FROM applications WHERE id = ?", (application_id,))
    log_event(db, actor, "application.erased", "application", application_id,
              f"{application['reference']} erased at trader request")
    db.commit()
    flash(request, f"{application['reference']} erased from the database.", "info")
    return RedirectResponse("/admin", status_code=303)


@router.get("/export.csv")
def export_csv(request: Request, db: sqlite3.Connection = Depends(get_db)):
    if (redirect := guard(request)):
        return redirect

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "reference", "business_name", "contact_name", "email", "phone",
        "category", "preferred_days", "stall_type", "power_required",
        "status", "submitted", "reviewer_note",
    ])
    for row in db.execute(
        """SELECT a.*, c.name AS category_name
             FROM applications a JOIN categories c ON c.id = a.category_id
            ORDER BY a.created_at"""
    ).fetchall():
        writer.writerow([
            row["reference"], row["business_name"], row["contact_name"], row["email"],
            row["phone"], row["category_name"], row["preferred_days"], row["stall_type"],
            "yes" if row["power_required"] else "no", row["status"], row["created_at"],
            row["reviewer_note"],
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=paisley-applications.csv"},
    )


@router.get("/audit")
def audit(request: Request, db: sqlite3.Connection = Depends(get_db)):
    if (redirect := guard(request)):
        return redirect
    events = db.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    return render(request, "admin/audit.html", {"market": MARKET, "events": events})
