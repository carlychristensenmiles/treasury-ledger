"""
Load the parsed fund CSVs in data/ into the Fund table.

Run once per year, whenever fresh tax-year PDFs from each fund family are
available: re-run the relevant data/parse_*.py script(s) to regenerate the
CSVs, then run this script again. It's idempotent -- re-running it for a
tax_year that's already loaded replaces those rows rather than duplicating
them, so it's safe to re-run after adding a new fund family or fixing a
parsing issue.

This is a thin CLI wrapper around app.seed.seed_funds -- the app itself
calls that same function automatically on startup if the Fund table is
empty (see app/main.py), so a fresh deployment seeds itself without this
script needing to be run manually. Use this script directly for local
development, or to force a re-seed (e.g. after updating a CSV) without
restarting the app.

Usage:
    python scripts/seed_db.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app.seed import seed_funds


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        summary = seed_funds(db)
    finally:
        db.close()

    for fname, count in summary["per_file"].items():
        if count:
            print(f"  loaded {count:>4} rows from {fname}")
        else:
            print(f"  (skip) {fname} not found or empty")

    print(f"\nSeed complete: {summary['total']} fund rows loaded for tax year(s): {summary['tax_years']}")


if __name__ == "__main__":
    main()
