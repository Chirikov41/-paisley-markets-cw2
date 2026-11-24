"""End-to-end tests for the Paisley Christmas Markets proof of concept."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')

VALID_APPLICATION = {
    "business_name": "Hogmanay Hampers",
    "contact_name": "Iona Fraser",
    "email": "iona@example.com",
    "phone": "0141 555 0100",
    "product_summary": "Hamper boxes of Scottish cheese, oatcakes and chutney, packed on the morning of trading.",
    "stall_type": "standard",
    "preferred_days": ["weekend-1"],
    "consent": "yes",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def csrf(client: TestClient, path: str = "/apply") -> str:
    response = client.get(path)
    match = CSRF_RE.search(response.text)
    assert match, f"no CSRF token on {path}"
    return match.group(1)


def fetch_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(os.environ["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def category_id(slug: str) -> int:
    return fetch_all("SELECT id FROM categories WHERE slug = ?", (slug,))[0]["id"]


def submit_application(client: TestClient, **overrides) -> object:
    payload = dict(VALID_APPLICATION)
    payload["category_id"] = str(category_id("food-drink"))
    payload["csrf_token"] = csrf(client)
    payload.update(overrides)
    return client.post("/apply", data=payload, follow_redirects=False)


def sign_in(client: TestClient) -> None:
    token = csrf(client, "/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "market2026", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303


# --------------------------------------------------------------------------- public


def test_home_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Paisley" in response.text
    assert "Apply for a pitch" in response.text
    assert "Featured traders" in response.text


def test_trader_directory_and_filters(client):
    assert client.get("/traders").status_code == 200

    food = client.get("/traders?category=food-drink")
    assert food.status_code == 200
    assert "The Gingerbread Room" in food.text
    assert "Coorie Ceramics" not in food.text

    weekend_two = client.get("/traders?day=weekend-2")
    assert weekend_two.status_code == 200
    assert "Coorie Ceramics" in weekend_two.text


def test_static_pages(client):
    assert client.get("/visit").status_code == 200
    privacy = client.get("/privacy")
    assert privacy.status_code == 200
    assert "lawful basis" in privacy.text.lower()


def test_unknown_page_uses_custom_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert "mulled wine" in response.text


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


# ------------------------------------------------------------------- applications


def test_apply_form_renders(client):
    response = client.get("/apply")
    assert response.status_code == 200
    assert 'action="/apply"' in response.text
    assert "privacy notice" in response.text


def test_application_validation_rejects_empty_form(client):
    response = client.post(
        "/apply",
        data={"csrf_token": csrf(client), "category_id": "", "preferred_days": []},
    )
    assert response.status_code == 422
    assert "This field is required." in response.text
    assert fetch_all("SELECT * FROM applications") == []


def test_application_validation_requires_consent(client):
    response = submit_application(client, consent="")
    assert response.status_code == 422
    assert "consent" in response.text.lower()
    assert fetch_all("SELECT * FROM applications") == []


def test_successful_application_creates_row_and_reference(client):
    response = submit_application(client)
    assert response.status_code == 303
    assert "/apply/success?ref=PCM-2026-" in response.headers["location"]

    rows = fetch_all("SELECT * FROM applications")
    assert len(rows) == 1
    assert rows[0]["reference"] == "PCM-2026-0001"
    assert rows[0]["status"] == "submitted"
    assert rows[0]["consent_given"] == 1
    assert rows[0]["consent_at"]

    confirmation = client.get(response.headers["location"])
    assert confirmation.status_code == 200
    assert "PCM-2026-0001" in confirmation.text


def test_duplicate_open_application_is_blocked(client):
    assert submit_application(client).status_code == 303
    duplicate = submit_application(client)
    assert duplicate.status_code == 422
    assert "already open" in duplicate.text
    assert len(fetch_all("SELECT * FROM applications")) == 1


def test_csrf_token_required(client):
    payload = dict(VALID_APPLICATION)
    payload["category_id"] = str(category_id("food-drink"))
    response = client.post("/apply", data=payload)
    assert response.status_code == 400


def test_status_lookup_matches_reference_and_email(client):
    submit_application(client)

    token = csrf(client, "/status")
    found = client.post(
        "/status",
        data={"reference": "PCM-2026-0001", "email": "iona@example.com", "csrf_token": token},
    )
    assert found.status_code == 200
    assert "Hogmanay Hampers" in found.text
    assert "Submitted" in found.text

    wrong_email = client.post(
        "/status",
        data={"reference": "PCM-2026-0001", "email": "someone@example.com", "csrf_token": token},
    )
    assert wrong_email.status_code == 422
    assert "could not match" in wrong_email.text.lower()


# ------------------------------------------------------------------------ admin


def test_admin_dashboard_requires_sign_in(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_admin_login_rejects_bad_password(client):
    token = csrf(client, "/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "wrong", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    page = client.get("/admin/login")
    assert "did not match" in page.text


def test_admin_login_and_dashboard(client):
    sign_in(client)
    page = client.get("/admin")
    assert page.status_code == 200
    assert "Trader applications" in page.text


def test_password_is_hashed_not_plain(client):
    row = fetch_all("SELECT password_hash FROM admins")[0]
    assert row["password_hash"].startswith("pbkdf2_sha256$")
    assert "market2026" not in row["password_hash"]


def test_admin_can_approve_application(client):
    submit_application(client)
    sign_in(client)

    detail = client.get("/admin/applications/1")
    token = CSRF_RE.search(detail.text).group(1)
    decision = client.post(
        "/admin/applications/1/decision",
        data={"decision": "approved", "note": "Pitch 14 reserved.", "csrf_token": token},
        follow_redirects=False,
    )
    assert decision.status_code == 303

    assert fetch_all("SELECT status FROM applications WHERE id = 1")[0]["status"] == "approved"
    assert fetch_all("SELECT action FROM audit_log WHERE action = 'application.approved'")

    token = csrf(client, "/status")
    status_page = client.post(
        "/status",
        data={"reference": "PCM-2026-0001", "email": "iona@example.com", "csrf_token": token},
    )
    assert "Approved" in status_page.text
    assert "Pitch 14 reserved." in status_page.text


def test_rejection_requires_a_reason(client):
    submit_application(client)
    sign_in(client)
    detail = client.get("/admin/applications/1")
    token = CSRF_RE.search(detail.text).group(1)

    response = client.post(
        "/admin/applications/1/decision",
        data={"decision": "rejected", "note": "no", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert fetch_all("SELECT status FROM applications WHERE id = 1")[0]["status"] == "submitted"


def test_csv_export_contains_application(client):
    submit_application(client)
    sign_in(client)
    response = client.get("/admin/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "PCM-2026-0001" in response.text
    assert "Hogmanay Hampers" in response.text


def test_erasure_removes_personal_data(client):
    submit_application(client)
    sign_in(client)
    detail = client.get("/admin/applications/1")
    token = CSRF_RE.search(detail.text).group(1)

    response = client.post(
        "/admin/applications/1/delete",
        data={"confirm": "DELETE", "csrf_token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert fetch_all("SELECT * FROM applications") == []
    assert fetch_all("SELECT action FROM audit_log WHERE action = 'application.erased'")
