"""Seed a handful of demo applications so the office dashboard has content.

Usage (from the project root):
    .venv\\Scripts\\python.exe scripts\\seed_demo.py

On a hosted instance the same data can be loaded at boot by setting the environment
variable SEED_DEMO=1, which is useful on platforms without a shell (for example the
Render free plan).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import connect, init_db  # noqa: E402
from app.demo_data import seed_demo_applications  # noqa: E402


def main() -> None:
    init_db()
    conn = connect()
    try:
        written = seed_demo_applications(conn, force=True)
        conn.commit()
        print(f"Seeded {written} demo applications.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
