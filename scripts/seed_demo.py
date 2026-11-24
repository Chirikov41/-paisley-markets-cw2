"""Seed a handful of demo applications so the office dashboard has content.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\seed_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import connect, init_db, utcnow  # noqa: E402

DEMO = [
    ("Hogmanay Hampers", "Iona Fraser", "iona@example.com", "0141 555 0100", "food-drink",
     "Hamper boxes of Scottish cheese, oatcakes and chutney, packed on the morning of trading.",
     "weekend-1,weekend-2", "standard", 1, "approved", "Pitch 14 reserved, invoice sent."),
    ("Clyde Chocolatier", "Marcus Reid", "marcus@example.com", "0141 555 0122", "food-drink",
     "Hand tempered tablet and chocolate bars, made in a Paisley kitchen in small batches.",
     "weekend-1", "standard", 0, "under_review", None),
    ("Wee Wooden Wonders", "Eilidh Munro", "eilidh@example.com", None, "crafts-gifts",
     "Scroll sawn decorations from reclaimed hardwood, personalised on request at the stall.",
     "weekend-2", "corner", 1, "submitted", None),
    ("Bratwurst Brothers", "Tomas Klein", "tomas@example.com", "0141 555 0144", "street-food",
     "Bratwurst and currywurst cooked over charcoal, with vegetarian option and allergen board.",
     "weekend-1,weekend-2", "food", 1, "approved", "Food hygiene certificate verified."),
    ("Paisley Print Collective", "Sarah Ahmed", "sarah@example.com", "0141 555 0166", "crafts-gifts",
     "Screen printed tea towels and prints of the Abbey, printed on the day in front of visitors.",
     "weekend-2", "standard", 0, "rejected",
     "Crafts and gifts category is full for weekend two, but weekend one has space."),
    ("Festive Faces", "Chloe Lamont", "chloe@example.com", None, "family",
     "Face painting and a quiet sensory craft corner for younger visitors and their families.",
     "weekend-1", "workshop", 1, "submitted", None),
]


def main() -> None:
    init_db()
    conn = connect()
    try:
        if conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]:
            print("Applications already exist - nothing to seed.")
            return
        for index, row in enumerate(DEMO, start=1):
            (business, contact, email, phone, slug, summary, days, stall, power,
             status, note) = row
            category = conn.execute("SELECT id FROM categories WHERE slug = ?", (slug,)).fetchone()
            now = utcnow()
            cursor = conn.execute(
                """INSERT INTO applications
                       (reference, business_name, contact_name, email, phone, category_id,
                        product_summary, preferred_days, stall_type, power_required, status,
                        reviewer_note, consent_given, consent_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                (f"PCM-2026-{9000 + index}", business, contact, email, phone, category["id"],
                 summary, days, stall, power, status, note, now, now, now),
            )
            conn.execute("UPDATE applications SET id = ? WHERE id = ?", (index, cursor.lastrowid))
        conn.commit()
        print(f"Seeded {len(DEMO)} demo applications.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
