import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point the app at a throwaway DB file BEFORE importing anything that touches app.database
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["TREASURY_LEDGER_DB"] = _tmp_db.name

from app.database import Base, engine, SessionLocal  # noqa: E402
from app.models import Fund  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    os.unlink(_tmp_db.name)


@pytest.fixture()
def db_session():
    """
    Yields a session, then wipes every table at teardown so tests are fully
    isolated regardless of whether the code under test calls session.commit()
    itself (app.seed.seed_funds does, by design -- the real CLI/startup-hook
    callers need an actual commit).

    A plain `session.rollback()` only undoes *uncommitted* work, so a
    committing fixture/function leaks rows into every later test sharing
    this on-disk temp DB -- confirmed the hard way: SQLite's pysqlite driver
    doesn't support SAVEPOINT-based isolation (SQLAlchemy's documented
    `join_transaction_mode="create_savepoint"` pattern) without extra
    driver-level event hooks to work around pysqlite's own implicit
    transaction handling, so that route wasn't worth the fragility here.
    Explicitly deleting every row after each test is simpler and reliable.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        cleanup = SessionLocal()
        try:
            for table in reversed(Base.metadata.sorted_tables):
                cleanup.execute(table.delete())
            cleanup.commit()
        finally:
            cleanup.close()


@pytest.fixture()
def sample_funds(db_session):
    """A handful of funds covering both asterisk conventions, for calc/matching tests."""
    funds = [
        Fund(family="Vanguard", ticker="VUSXX", name="Vanguard Treasury Money Market Fund",
             pct_govt_obligations=100.0, meets_ca_ct_ny=True, tax_year=2025),
        Fund(family="Vanguard", ticker="BND", name="Vanguard Total Bond Market ETF",
             pct_govt_obligations=44.06, meets_ca_ct_ny=False, tax_year=2025),
        # Fidelity fund whose source PDF marked it with an asterisk, meaning it
        # FAILS the CA/CT/NY threshold -- verifying the inversion is handled upstream.
        Fund(family="Fidelity", ticker=None, fund_number="6497", cusip="316069244",
             name="30% Allocation Fund", pct_govt_obligations=38.5630,
             meets_ca_ct_ny=False, tax_year=2025),
        Fund(family="PIMCO", ticker=None, name="PIMCO Long-Term U.S. Government Fund",
             pct_govt_obligations=88.59, meets_ca_ct_ny=True, tax_year=2025),
    ]
    for f in funds:
        db_session.add(f)
    db_session.commit()
    return funds
