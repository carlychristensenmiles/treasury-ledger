# Treasury Ledger

Bond ETFs and money-market funds report their income to shareholders as
"dividends" on Form 1099-DIV, not as direct interest on Form 1099-INT — even
when a real portion of that income came from direct U.S. government
obligations (Treasuries, agency debt, etc.), which is exempt from state
income tax in most states. Each fund family publishes, once a year, the
exact percentage of its distributions that qualifies. Nobody applies it
unless someone manually cross-references every fund a client holds against
that fund family's own tax-information PDF.

Treasury Ledger does that calculation automatically:

```
state-tax-exempt amount = 1099-DIV Box 1a ordinary dividends
                           × fund's published % of income from direct U.S. government obligations
```

against a backend database of those percentages, gathered once per year from
each fund family's own investor tax documents.

## What it does

1. **Login** — email/password accounts, one per firm/user.
2. **Upload a 1099-DIV (or similar) PDF** — pages are read directly when the
   PDF has a text layer, and **OCR'd automatically** when they don't (a
   scanned or image-only PDF). This isn't a hypothetical: one of the five
   fund-family tax documents used to seed this app's own database (Schwab's)
   turned out to be a genuinely scanned, text-layer-free PDF, and it's
   processed through the exact same OCR path as a user's upload. See
   `data/README.md` for how that was confirmed and handled.
3. **Review extracted holdings** — the scan surfaces candidate
   ticker + dollar-amount rows for the user to confirm, edit, or drop before
   anything is saved; nothing commits automatically.
4. **The calculation** — each confirmed holding is matched against the fund
   database (by ticker, CUSIP, or fuzzy name) and multiplied by that fund's
   percentage, per client, with a toggle for the stricter CA/CT/NY rule
   (only funds meeting a 50%-of-assets-at-every-quarter-end threshold pass
   the exemption through in those three states).

## Data: gathered once a year, not per upload

`data/` contains the actual source PDFs from five major fund families
(Fidelity, Vanguard, Schwab, iShares, PIMCO — 2025 tax year), the scripts
that turned each one into a clean CSV, and `scripts/seed_db.py`, which loads
all ~1,900 resulting fund rows into the app's database. **This is the "back
end database, gathered once per year" the product is built around** — see
`data/README.md` for full sourcing notes, including a fund-family-specific
gotcha (Fidelity marks the CA/CT/NY-qualifying asterisk in the *opposite*
direction from every other family) that's resolved once at parse time so no
other part of the app has to know about it.

## Running it locally

Requires Python 3.11+, and Tesseract OCR + Poppler's `pdftoppm`/`pdftotext`
installed as system packages (used for the OCR fallback and for the yearly
data-refresh scripts):

```bash
# macOS
brew install tesseract poppler
# Debian/Ubuntu
sudo apt-get install -y tesseract-ocr poppler-utils
```

Then:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python scripts/seed_db.py          # loads data/funds_*.csv into a new treasury_ledger.db
SECRET_KEY=change-me uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000`, create an account, add a client, and upload a
1099-DIV (or add holdings by hand from a ticker + dollar amount).

Set `SECRET_KEY` to a real random value before using this anywhere but your
own machine — it signs the login session cookie. `TREASURY_LEDGER_DB` can
point the app at a different SQLite file path (the test suite uses this to
run against a throwaway database).

## Running the tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Covers the calculation engine (including the Fidelity asterisk-inversion
case, and the CA/CT/NY threshold rule), fund lookup by ticker/CUSIP/fuzzy
name, and PDF text extraction — including a synthetic image-only PDF built
in the test itself to exercise the OCR fallback path without depending on
any external file.

## Architecture

- **FastAPI + Jinja2** server-rendered templates (no separate frontend
  build step — simpler to run locally and to hand off).
- **SQLite + SQLAlchemy** — zero-config, a single file on disk.
- **Session-cookie auth** (Starlette's signed-cookie sessions + passlib/
  bcrypt password hashing) — no third-party auth dependency.
- **PyMuPDF (`fitz`) + pytesseract** for PDF text extraction with OCR
  fallback (`app/pdf_processing.py`).
- **`app/calculations.py`** is the one place the actual tax math lives —
  kept deliberately small and dependency-free so it's easy to audit and to
  test in isolation from the web layer.

```
app/
  main.py            FastAPI app setup, session middleware, routing
  database.py        SQLAlchemy engine/session
  models.py           User, Client, Fund, Upload, Holding
  auth.py             password hashing + session helpers
  calculations.py     the exemption calculation + fund lookup (ticker/CUSIP/fuzzy name)
  pdf_processing.py   text extraction with OCR fallback + candidate holding extraction
  routes/              auth, dashboard, clients, upload/review
  templates/, static/  Jinja2 templates + one stylesheet
data/                 source PDFs, per-family parsers, output CSVs (see data/README.md)
scripts/seed_db.py    loads data/funds_*.csv into the database
tests/                 pytest suite
```

## What's not built yet

- No live hosting — this is a complete, runnable, tested codebase meant to
  be deployed by whoever picks it up next (see the business-plan questions
  around target market/pricing that are still open).
- No password reset flow, no multi-user firm accounts (one login = one set
  of clients), no CSV/PDF export of results yet.
- Ticker coverage gaps for PIMCO and most Fidelity funds (see
  `data/README.md` → Known limitations) — those funds still work via
  fuzzy-name matching or manual entry, just not by ticker lookup yet.
- Fund data currently covers tax year 2025 only, for five fund families.
  Re-running the yearly refresh (`data/README.md` → "Updating for a new tax
  year") is a manual, once-a-year step, not automated.
