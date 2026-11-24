"""Public-facing pages: home, trader directory, visiting information, privacy notice."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request

from ..content import MARKET
from ..core import render
from ..db import get_db

router = APIRouter()


def _featured(db: sqlite3.Connection):
    return db.execute(
        """SELECT t.*, c.name AS category_name
             FROM traders t JOIN categories c ON c.id = t.category_id
            WHERE t.featured = 1
            ORDER BY c.name, t.name"""
    ).fetchall()


def _stats(db: sqlite3.Connection) -> dict:
    return {
        "traders": db.execute("SELECT COUNT(*) FROM traders").fetchone()[0],
        "categories": db.execute("SELECT COUNT(*) FROM categories").fetchone()[0],
        "approved": db.execute(
            "SELECT COUNT(*) FROM applications WHERE status = 'approved'"
        ).fetchone()[0],
    }


@router.get("/")
def home(request: Request, db: sqlite3.Connection = Depends(get_db)):
    return render(
        request,
        "index.html",
        {
            "featured": _featured(db),
            "stats": _stats(db),
            "market": MARKET,
        },
    )


@router.get("/traders")
def traders(
    request: Request,
    db: sqlite3.Connection = Depends(get_db),
    category: str | None = None,
    day: str | None = None,
):
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    sql = """SELECT t.*, c.name AS category_name, c.slug AS category_slug
               FROM traders t JOIN categories c ON c.id = t.category_id
              WHERE 1 = 1"""
    params: list[str] = []
    if category:
        sql += " AND c.slug = ?"
        params.append(category)
    if day in {"weekend-1", "weekend-2"}:
        sql += " AND (t.trading_days = ? OR t.trading_days = 'both')"
        params.append(day)
    sql += " ORDER BY c.name, t.name"

    return render(
        request,
        "traders.html",
        {
            "market": MARKET,
            "traders": db.execute(sql, params).fetchall(),
            "categories": categories,
            "active_category": category,
            "active_day": day,
            "total": db.execute("SELECT COUNT(*) FROM traders").fetchone()[0],
        },
    )


@router.get("/visit")
def visit(request: Request):
    return render(request, "visit.html", {"market": MARKET})


@router.get("/privacy")
def privacy(request: Request):
    return render(request, "privacy.html", {"market": MARKET})
