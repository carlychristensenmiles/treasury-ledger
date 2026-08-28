"""
Load the parsed fund CSVs in data/ into the Fund table.

Run once per year, whenever fresh tax-year PDFs from each fund family are
available: re-run the relevant data/parse_*.py script(s) to regenerate the
CSVs, then run this script again. It's idempotent -- re-running it for a
tax_year that's already loaded replaces those rows rather than duplicating
them, so it's safe to re-run after adding a new fund family or fixing a
parsing issue.

Usage:
    python scripts/seed_db.py
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app.models import Fund

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

CSV_FILES = [
    "funds_fidelity.csv",
    "funds_vanguard.csv",
    "funds_ishares.csv",
    "funds_schwab.csv",
    "funds_pimco.csv",
]


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    years_touched = set()
    total = 0
    try:
        for fname in CSV_FILES:
            path = os.path.join(DATA_DIR, fname)
            if not os.path.exists(path):
                print(f"  (skip) {fname} not found")
                continue
            rows = load_csv(path)
            if not rows:
                continue
            tax_year = int(rows[0]["tax_year"])
            years_touched.add(tax_year)

            for row in rows:
                ticker = (row.get("ticker") or "").strip().upper() or None
                fund_number = (row.get("fund_number") or "").strip() or None
                cusip = (row.get("cusip") or "").strip().upper() or None

                existing = (
                    db.query(Fund)
                    .filter(
                        Fund.family == row["family"],
                        Fund.ticker == ticker,
                        Fund.fund_number == fund_number,
                        Fund.tax_year == tax_year,
                    )
                    .first()
                )
                if existing:
                    fund = existing
                else:
                    fund = Fund(family=row["family"], ticker=ticker, fund_number=fund_number, tax_year=tax_year)
                    db.add(fund)

                fund.cusip = cusip
                fund.name = row["name"]
                fund.pct_govt_obligations = float(row["pct_govt_obligations"])
                fund.meets_ca_ct_ny = row["meets_ca_ct_ny"] == "1"
                total += 1

            print(f"  loaded {len(rows):>4} rows from {fname}")

        db.commit()
    finally:
        db.close()

    print(f"\nSeed complete: {total} fund rows loaded for tax year(s): {sorted(years_touched)}")


if __name__ == "__main__":
    main()
