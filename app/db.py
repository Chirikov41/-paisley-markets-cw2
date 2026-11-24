"""SQLite access helpers and first-run seeding."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def database_path() -> Path:
    """Location of the SQLite file (override with DATABASE_PATH for deployment)."""
    configured = os.getenv("DATABASE_PATH")
    return Path(configured) if configured else BASE_DIR / "data" / "market.db"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False is safe here: every request gets its own connection,
    # and FastAPI may run the dependency and the endpoint handler on different threads.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


CATEGORY_SEED = [
    ("food-drink", "Food & Drink", "Hot food, bakes, sweets and seasonal drinks."),
    ("crafts-gifts", "Crafts & Gifts", "Handmade gifts, ceramics, woodwork and textiles."),
    ("festive-decor", "Festive Decorations", "Trees, wreaths, lights and table decorations."),
    ("street-food", "Street Food", "Outdoor cooking, loaded fries, bratwurst and crepes."),
    ("family", "Family & Children", "Craft workshops, face painting and story sessions."),
]

TRADER_SEED = [
    ("Thornliebank Bratwurst Co.", "street-food", "Pitch 12, Abbey Close", "both",
     "Charcoal-grilled bratwurst with sauerkraut and mustard, served from a timber hut.", None, 1),
    ("The Gingerbread Room", "food-drink", "Pitch 4, Town Hall Square", "both",
     "Small-batch gingerbread, stollen and hot chocolate with a marshmallow garnish.", None, 1),
    ("Coorie Ceramics", "crafts-gifts", "Pitch 21, High Street", "weekend-2",
     "Wheel-thrown mugs and tree decorations glazed in winter greens and heather.", None, 0),
    ("Rowan & Rye Wreaths", "festive-decor", "Pitch 8, Abbey Close", "weekend-1",
     "Living wreaths made on the premises, plus dried citrus garlands.", None, 0),
    ("Paisley Weavers' Wool", "crafts-gifts", "Pitch 17, High Street", "both",
     "Hand-dyed yarn inspired by the town's weaving heritage, with beginner kits.", None, 1),
    ("The Crepe Ski Lodge", "street-food", "Pitch 9, Town Hall Square", "both",
     "Sweet and savoury crepes cooked to order, with gluhwein for adults.", None, 0),
    ("Little Elves Workshop", "family", "Pitch 2, Family Marquee", "both",
     "Drop-in card making and letter writing to Father Christmas, 30 minute sessions.", None, 0),
    ("Abbey Ales & Mulled Wine", "food-drink", "Pitch 6, Abbey Close", "both",
     "Local craft ales, mulled cider and a rotating guest tap each weekend.", None, 1),
    ("Fir & Frost Florals", "festive-decor", "Pitch 15, High Street", "weekend-2",
     "Table centrepieces, stair garlands and pre-lit potted trees.", None, 0),
    ("Snowcake Bakery", "food-drink", "Pitch 3, Town Hall Square", "weekend-1",
     "Cinnamon buns, mince pies and a signature white chocolate snowcake.", None, 0),
]


def _seed(conn: sqlite3.Connection) -> None:
    from .security import hash_password

    conn.executemany(
        "INSERT OR IGNORE INTO categories (slug, name, description) VALUES (?, ?, ?)",
        CATEGORY_SEED,
    )

    if conn.execute("SELECT COUNT(*) FROM traders").fetchone()[0] == 0:
        rows = []
        for name, slug, pitch, days, description, website, featured in TRADER_SEED:
            category = conn.execute("SELECT id FROM categories WHERE slug = ?", (slug,)).fetchone()
            rows.append((name, category["id"], pitch, days, description, website, featured))
        conn.executemany(
            """INSERT INTO traders (name, category_id, pitch, trading_days, description, website, featured)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )

    if conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "market2026")
        conn.execute(
            "INSERT INTO admins (username, display_name, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, "Market Office", hash_password(password), utcnow()),
        )


def init_db() -> None:
    """Create tables and seed reference data. Safe to call on every boot."""
    conn = connect()
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _seed(conn)
        conn.commit()
    finally:
        conn.close()


def log_event(conn: sqlite3.Connection, actor: str, action: str, entity: str,
              entity_id: int | None = None, detail: str | None = None) -> None:
    conn.execute(
        """INSERT INTO audit_log (actor, action, entity, entity_id, detail, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (actor, action, entity, entity_id, detail, utcnow()),
    )
