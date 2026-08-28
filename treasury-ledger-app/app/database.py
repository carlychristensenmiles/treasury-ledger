"""
SQLAlchemy engine/session setup. Zero-config: a single SQLite file on disk.

The DB file path can be overridden with the TREASURY_LEDGER_DB env var, which
tests use to point at a temporary throwaway database.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = os.environ.get("TREASURY_LEDGER_DB", "treasury_ledger.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
