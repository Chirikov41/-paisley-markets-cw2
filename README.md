# Paisley Christmas Markets - proof of concept

A working web application built for **COMP10020 Internet Technologies, Coursework 2**.
The brief asks for a site specification plus a proof of concept that shows a realistic
trader application workflow with database interaction. This repository contains the
proof of concept; the specification document is submitted separately.

The market is fictional. The scenario: a software house is tendering to build a site for
a community group running *Paisley Christmas Markets*, and wants a generic pattern that
can be reused for other seasonal events.

---

## What the site does

**For visitors**

- Home page with the two market weekends, featured traders and an application explainer
- Trader directory with category and weekend filters
- Visiting information: opening hours, travel, access, quiet hour
- Privacy notice written against the UK GDPR headings used in the report

**For traders**

- Full application form with server side validation, inline errors and an error summary
- Consent captured with a timestamp, and a duplicate-application guard per business
- Immediate reference number (for example `PCM-2026-0001`) and a confirmation page
- Status lookup using reference **and** email, so one trader cannot read another's record

**For the market office (administrator)**

- Session based sign in with hashed passwords and a failed-attempt counter
- Dashboard with status tabs, counts and search
- Application detail with approve / reject / mark under review, plus a note shown to the trader
- GDPR erasure action that deletes the record and writes the deletion to an audit log
- CSV export of every application
- Audit log of sign ins, decisions and erasures

---

## Quick start

Requires Python 3.10 or newer.

```powershell
# Windows PowerShell, from the project folder
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

```bash
# macOS / Linux
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

| Area | Address |
| --- | --- |
| Public site | <http://127.0.0.1:8000/> |
| Trader application | <http://127.0.0.1:8000/apply> |
| Application status | <http://127.0.0.1:8000/status> |
| Market office | <http://127.0.0.1:8000/admin/login> |
| OpenAPI schema | <http://127.0.0.1:8000/docs> |

The database is created and seeded on first start at `data/market.db`.
Delete that file to start again.

### Demo credentials

```
username: admin
password: market2026
```

Override before the first run with `ADMIN_USERNAME` and `ADMIN_PASSWORD`, and set
`SECRET_KEY` to a long random value in any deployment.

### Demo data

To fill the office dashboard with realistic applications:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

---

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The suite covers the public pages, form validation, consent handling, duplicate
protection, CSRF rejection, the status lookup, administrator sign in, approve and reject
rules, CSV export and GDPR erasure. Each test runs against a temporary SQLite file.

---

## Project structure

```
app/
  main.py          application factory, middleware, static files
  db.py            connection handling, schema creation, seeding
  schema.sql       tables, constraints and indexes
  content.py       market copy shared by the templates
  core.py          Jinja environment, flash messages, safe redirects
  security.py      PBKDF2 password hashing, CSRF tokens, session helpers
  routes/
    public.py      home, trader directory, visiting, privacy
    apply.py       application form, confirmation, status lookup
    admin.py       sign in, dashboard, decisions, erasure, CSV, audit
  templates/       Jinja2 templates (public and admin)
  static/css/      hand written stylesheet
scripts/seed_demo.py
tests/test_app.py
render.yaml        deployment blueprint
```

## Data model

| Table | Purpose |
| --- | --- |
| `categories` | Stall categories used by the directory and the form |
| `traders` | Confirmed traders shown in the public directory |
| `applications` | Trader applications, consent timestamp, status and reviewer note |
| `admins` | Market office accounts with PBKDF2-SHA256 password hashes |
| `audit_log` | Who did what, when: sign ins, decisions, erasures |

Relations: `traders.category_id` and `applications.category_id` reference `categories.id`.
`audit_log.entity_id` points at `applications.id` for application events.

## Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Home |
| GET | `/traders` | Directory with `category` and `day` filters |
| GET | `/visit` | Visiting information |
| GET | `/privacy` | Privacy notice |
| GET | `/apply` | Application form |
| POST | `/apply` | Validate and store an application |
| GET | `/apply/success` | Confirmation with reference |
| GET | `/status` | Status lookup form |
| POST | `/status` | Status lookup by reference and email |
| GET | `/admin/login` | Office sign in |
| POST | `/admin/login` | Authenticate |
| POST | `/admin/logout` | End session |
| GET | `/admin` | Dashboard, filters and search |
| GET | `/admin/applications/{id}` | Application detail and history |
| POST | `/admin/applications/{id}/decision` | Approve, reject or mark under review |
| POST | `/admin/applications/{id}/delete` | GDPR erasure |
| GET | `/admin/export.csv` | CSV export |
| GET | `/admin/audit` | Audit log |
| GET | `/healthz` | Health check for hosting |

## Security and data protection notes

- Passwords are stored as `pbkdf2_sha256$260000$salt$hash`, never in plain text.
- Every state changing form carries a per-session CSRF token; a missing or stale token
  returns 400.
- Session cookies are signed with `SECRET_KEY`, `SameSite=Lax`, and `Secure` when
  `SESSION_HTTPS_ONLY=1` is set in deployment.
- The status page requires both the reference and the email address, so a guessed
  reference alone reveals nothing.
- Admin actions and failed sign ins are written to `audit_log`.
- Erasure removes the application row; the audit entry that records the erasure keeps no
  personal data beyond the reference.

## Deployment

`render.yaml` describes a free Render web service that installs `requirements.txt` and
runs `uvicorn app.main:app`. On Render's free plan the filesystem is ephemeral, so the
SQLite file is recreated on each deploy; that is acceptable for a proof of concept.
A paid instance with a persistent disk, or a managed PostgreSQL database, would be the
next step (see the Hosting section of the specification).

To deploy manually on any platform that runs Python:

1. Set `SECRET_KEY` to a long random string.
2. Set `ADMIN_PASSWORD` before the first boot so the default password is never used.
3. Start with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

## Attribution

Built for COMP10020 Internet Technologies (University of the West of Scotland).
Framework documentation referenced: FastAPI, Jinja2, Starlette and SQLite.
The market, its traders and the applications in `scripts/seed_demo.py` are fictional.
