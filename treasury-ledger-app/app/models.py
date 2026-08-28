"""
SQLAlchemy models.

Fund.meets_ca_ct_ny is a NORMALIZED boolean with one consistent meaning
everywhere in this codebase: True = the fund meets the CA/CT/NY 50%-of-assets
threshold and its government-obligation income may pass through to residents
of those three states. Each fund family marks this differently in its source
PDF (Vanguard/iShares/Schwab/PIMCO use an asterisk for "meets"; Fidelity
uniquely uses an asterisk for "does NOT meet") -- that inversion is resolved
once, at seed-data-parsing time (see data/parse_fidelity.py), specifically so
no code downstream of this model ever has to know about per-family asterisk
conventions again.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    firm_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    clients = relationship("Client", back_populates="user", cascade="all, delete-orphan")
    uploads = relationship("Upload", back_populates="user", cascade="all, delete-orphan")


class Client(Base):
    """A CPA firm's / advisor's end client (taxpayer) whose 1099s are analyzed."""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    state = Column(String(2), nullable=True)  # optional 2-letter state code, for CA/CT/NY handling
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="clients")
    holdings = relationship("Holding", back_populates="client", cascade="all, delete-orphan")


class Fund(Base):
    """
    One row per (fund family, ticker OR fund_number, tax_year): the published
    percentage of ordinary dividend income derived from direct U.S. government
    obligations, gathered once per year from each fund family's own investor
    tax-information PDF. This is the backend database the whole product is
    built around -- see data/README.md for sourcing and data/parse_*.py for
    how each family's PDF was turned into this table.
    """
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True)
    family = Column(String(64), nullable=False, index=True)
    ticker = Column(String(16), nullable=True, index=True)  # blank for funds whose source doc omits a ticker
    fund_number = Column(String(16), nullable=True)  # Fidelity-specific internal fund number
    cusip = Column(String(16), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    pct_govt_obligations = Column(Float, nullable=False)  # 0-100
    meets_ca_ct_ny = Column(Boolean, nullable=False, default=False)
    tax_year = Column(Integer, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("family", "ticker", "fund_number", "tax_year", name="uq_fund_identity_year"),
    )


class Upload(Base):
    """A single 1099-DIV (or similar) PDF a user uploaded for processing."""
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    filename = Column(String(255), nullable=False)
    status = Column(String(32), default="processed")  # processed | failed
    page_count = Column(Integer, nullable=True)
    ocr_page_count = Column(Integer, nullable=True)  # how many pages needed OCR fallback
    extracted_text_preview = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="uploads")
    holdings = relationship("Holding", back_populates="upload", cascade="all, delete-orphan")


class Holding(Base):
    """
    One extracted (or manually entered) line from a 1099-DIV: a fund ticker
    plus its Box 1a ordinary dividend amount, and the calculation result:
    ordinary_dividends x fund's pct_govt_obligations = state-tax-exempt amount.
    """
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey("uploads.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    fund_id = Column(Integer, ForeignKey("funds.id"), nullable=True)

    ticker_raw = Column(String(64), nullable=True)   # as extracted/typed by the user
    name_raw = Column(String(255), nullable=True)
    ordinary_dividends = Column(Float, nullable=False, default=0.0)  # Box 1a amount

    matched = Column(Boolean, default=False)
    pct_used = Column(Float, nullable=True)          # % applied at calc time (snapshot, in case Fund data changes later)
    exempt_amount = Column(Float, nullable=True)      # ordinary_dividends * pct_used / 100
    cactny_restricted = Column(Boolean, default=False)  # True if state_mode=CACTNY and fund doesn't meet threshold -> exempt forced to 0

    created_at = Column(DateTime, default=utcnow)

    client = relationship("Client", back_populates="holdings")
    upload = relationship("Upload", back_populates="holdings")
    fund = relationship("Fund")
