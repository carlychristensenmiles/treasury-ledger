import csv
import os

from app.models import Fund
from app.seed import seed_funds, funds_table_is_empty

CSV_HEADER = ["family", "ticker", "fund_number", "cusip", "name", "pct_govt_obligations", "meets_ca_ct_ny", "tax_year"]


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def test_funds_table_is_empty_true_on_fresh_db(db_session):
    assert funds_table_is_empty(db_session) is True


def test_funds_table_is_empty_false_after_seeding(db_session, sample_funds):
    assert funds_table_is_empty(db_session) is False


def test_seed_funds_loads_rows_from_csv(db_session, tmp_path):
    csv_path = tmp_path / "funds_test.csv"
    _write_csv(str(csv_path), [
        {"family": "TestFam", "ticker": "TSTX", "fund_number": "", "cusip": "",
         "name": "Test Fund", "pct_govt_obligations": "50.0000", "meets_ca_ct_ny": "1", "tax_year": "2025"},
    ])
    summary = seed_funds(db_session, data_dir=str(tmp_path), csv_files=["funds_test.csv"])
    assert summary["total"] == 1
    assert summary["tax_years"] == [2025]

    fund = db_session.query(Fund).filter(Fund.ticker == "TSTX").first()
    assert fund is not None
    assert fund.pct_govt_obligations == 50.0
    assert fund.meets_ca_ct_ny is True


def test_seed_funds_is_idempotent(db_session, tmp_path):
    """Re-running seed_funds for the same (family, ticker, fund_number, tax_year)
    updates the existing row in place rather than creating a duplicate --
    this is what makes it safe to call automatically on every app startup."""
    csv_path = tmp_path / "funds_test.csv"
    _write_csv(str(csv_path), [
        {"family": "TestFam", "ticker": "TSTX", "fund_number": "", "cusip": "",
         "name": "Test Fund", "pct_govt_obligations": "50.0000", "meets_ca_ct_ny": "1", "tax_year": "2025"},
    ])
    seed_funds(db_session, data_dir=str(tmp_path), csv_files=["funds_test.csv"])
    seed_funds(db_session, data_dir=str(tmp_path), csv_files=["funds_test.csv"])

    matches = db_session.query(Fund).filter(Fund.ticker == "TSTX").all()
    assert len(matches) == 1


def test_seed_funds_updates_changed_percentage(db_session, tmp_path):
    csv_path = tmp_path / "funds_test.csv"
    _write_csv(str(csv_path), [
        {"family": "TestFam", "ticker": "TSTX", "fund_number": "", "cusip": "",
         "name": "Test Fund", "pct_govt_obligations": "50.0000", "meets_ca_ct_ny": "1", "tax_year": "2025"},
    ])
    seed_funds(db_session, data_dir=str(tmp_path), csv_files=["funds_test.csv"])

    _write_csv(str(csv_path), [
        {"family": "TestFam", "ticker": "TSTX", "fund_number": "", "cusip": "",
         "name": "Test Fund", "pct_govt_obligations": "61.5000", "meets_ca_ct_ny": "0", "tax_year": "2025"},
    ])
    seed_funds(db_session, data_dir=str(tmp_path), csv_files=["funds_test.csv"])

    fund = db_session.query(Fund).filter(Fund.ticker == "TSTX").one()
    assert fund.pct_govt_obligations == 61.5
    assert fund.meets_ca_ct_ny is False


def test_seed_funds_skips_missing_file_gracefully(db_session, tmp_path):
    summary = seed_funds(db_session, data_dir=str(tmp_path), csv_files=["does_not_exist.csv"])
    assert summary["total"] == 0
