"""
Shared logic for loading data/funds_*.csv into the Fund table. Used by both
scripts/seed_db.py (manual/local re-seeding) and app.main's startup hook
(automatic first-boot seeding on a fresh deployment -- see the note in
app/main.py about why this matters on a platform like Fly.io, where a
one-off `flyctl ssh console` step is easy to forget on a fresh volume).

Idempotent: safe to call on every app startup. Re-running it for a
(family, ticker, fund_number, tax_year) that's already loaded updates that
row in place rather than duplicating it.
"""
import csv
import os

from sqlalchemy.orm import Session

from app.models import Fund

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

CSV_FILES = [
    "funds_fidelity.csv",
    "funds_vanguard.csv",
    "funds_ishares.csv",
    "funds_schwab.csv",
    "funds_pimco.csv",
]


def _load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def seed_funds(db: Session, data_dir: str = DATA_DIR, csv_files=CSV_FILES) -> dict:
    """
    Load every data/funds_*.csv into the Fund table. Returns a small summary
    dict (rows loaded per file, tax years touched, total) for logging.
    """
    years_touched = set()
    total = 0
    per_file = {}

    for fname in csv_files:
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            per_file[fname] = 0
            continue
        rows = _load_csv(path)
        if not rows:
            per_file[fname] = 0
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

        per_file[fname] = len(rows)

    db.commit()
    return {"per_file": per_file, "tax_years": sorted(years_touched), "total": total}


def funds_table_is_empty(db: Session) -> bool:
    return db.query(Fund.id).first() is None
