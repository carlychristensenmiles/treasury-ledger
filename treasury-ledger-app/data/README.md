# Fund government-obligation data

This directory is the "gather once per year" backend data source the whole
product is built around: for each fund family, the percentage of ordinary
dividend income derived from direct U.S. government obligations, published
annually in that family's own investor tax-information document.

## Layout

```
data/
  source_pdfs/          the original PDFs as published by each fund family (2025 tax year)
  *_raw.txt              plain text extracted from each source PDF (see "How each was produced" below)
  parse_*.py              one script per family: raw text/PDF -> funds_*.csv
  funds_*.csv             the cleaned, normalized output -- what scripts/seed_db.py actually loads
  schwab_pages/           (gitignored) rasterized page images used to OCR the Schwab PDF; regenerate with the command below, not committed
```

`funds_*.csv` columns: `family, ticker, fund_number, cusip, name, pct_govt_obligations, meets_ca_ct_ny, tax_year`.

`meets_ca_ct_ny` is a **normalized** boolean, True meaning the fund meets the
CA/CT/NY 50%-of-assets-at-every-quarter-end threshold required for the
exemption to pass through to residents of those three states. See "The
asterisk problem" below -- this column is what lets every other part of the
codebase forget that problem ever existed.

## How each source PDF was produced / read

- **Vanguard, Fidelity, PIMCO, iShares**: each source PDF has a normal text
  layer. `pdftotext -layout data/source_pdfs/<family>_2025.pdf data/<family>_raw.txt`
  reproduces the `*_raw.txt` files (Vanguard's parser reads the PDF directly
  with `pdfplumber` instead, for reasons below).
- **Schwab**: the source PDF has **no text layer at all** -- confirmed with
  `pdfimages -list data/source_pdfs/schwab_2025.pdf`, which shows one
  full-page image per page. It was rasterized and OCR'd:
  ```
  pdftoppm -r 300 -png data/source_pdfs/schwab_2025.pdf data/schwab_pages/page
  for f in data/schwab_pages/*.png; do tesseract "$f" - --psm 6; done > data/schwab_raw.txt
  ```
  This is the exact same text-layer-first / OCR-fallback strategy
  `app/pdf_processing.py` uses on a user's uploaded 1099s -- Schwab's own tax
  document turned out to be a perfect real-world test case for it.

## Per-family parsing notes

- **Fidelity** (`parse_fidelity.py`): the cleanest tabular layout of the
  five, but publishes **no ticker symbol** -- only an internal "Fund Number"
  and CUSIP. ~939 fund/share-class rows. Funds are matched in the app by
  CUSIP or by fuzzy name match; there is no ticker-based lookup for
  Fidelity funds until a ticker↔CUSIP mapping is curated (see Known
  limitations).
- **Vanguard** (`parse_vanguard.py`): the PDF renders the fund table as two
  side-by-side columns per page with fund names that sometimes wrap onto a
  second line. A naive `pdftotext -layout` merges both columns onto shared
  text lines and scrambles which percentage belongs to which fund -- so this
  parser uses `pdfplumber` word-level bounding boxes instead, splitting each
  page into a left/right column band by x-position and reconstructing rows
  by y-position. It also had to work out, empirically, which direction a
  wrapped continuation line belongs (see the comment in the script): a bare
  continuation line always finishes the *previous* row's name, never
  prefixes the next one. Verified against the source PDF text directly for
  a case (VMRXX / VCMDX) where getting this backwards would have put the
  wrong fund's asterisk -- and therefore its CA/CT/NY eligibility -- on the
  wrong fund. 359 funds.
- **iShares** (`parse_ishares.py`): single column, straightforward. 452
  funds.
- **Schwab** (`parse_schwab.py`): only ~29 distinct funds (57 rows after
  expanding multi-share-class tickers like `SWGXX/SNVXX/SGUXX`), so instead
  of regex-parsing noisy OCR text, each row was hand-transcribed and
  verified against the OCR output and the rendered page images -- safer than
  trusting a regex against OCR artifacts (the OCR text itself has at least
  one obvious error: "44 06%" for "44.06%"). Money-market funds that publish
  one percentage across several share-class tickers are expanded into one
  CSV row per ticker.
- **PIMCO** (`parse_pimco.py`): like Fidelity, publishes fund **names only,
  no tickers**, across five sub-tables (open-end funds, equity series,
  closed-end funds, interval funds, ETFs, Fixed Income SHares). Rows with
  no percentage ("-", meaning 0%/not applicable) are dropped, matching how
  Schwab's doc explicitly states "funds not shown had 0%". 111 funds.
  **We deliberately did not hand-map ticker symbols from general knowledge**
  for PIMCO's well-known ETFs (e.g. the fund named "PIMCO Active Bond
  Exchange-Traded Fund") even though several are easy to recognize --
  a wrong guess here would silently misapply a tax percentage, which is
  worse than no match at all. These are matched by fuzzy name instead.

## The asterisk problem

Every fund family marks, with an asterisk (or double asterisk), whether a
fund meets the CA/CT/NY 50%-of-assets threshold -- but **the direction is
not consistent across families**:

| Family    | Marker | Meaning                                    |
|-----------|--------|---------------------------------------------|
| Vanguard  | `*`    | fund **meets** the threshold (qualifies)     |
| iShares   | `**`   | fund **meets** the threshold (qualifies)     |
| Schwab    | `*`    | fund **meets** the threshold (qualifies)     |
| PIMCO     | `*`    | fund **meets** the threshold (qualifies)     |
| Fidelity  | `*`    | fund **DID NOT meet** the threshold (fails) — the odd one out |

This is resolved exactly once, in `parse_fidelity.py`, by inverting the
boolean at parse time so that `meets_ca_ct_ny=True` means the same thing in
every row of every `funds_*.csv` file. `app/calculations.py` and every
route/template downstream only ever reads that already-normalized column --
nowhere else in the codebase needs to know a per-family convention exists.
This is covered directly by
`tests/test_calculations.py::test_fidelity_asterisk_inversion_is_already_normalized`.

## Known limitations / not yet resolved

- **PIMCO and most Fidelity funds have no ticker in the seed data.** A
  user's actual 1099-DIV almost always shows a ticker, not a CUSIP or
  Fidelity's internal fund number, so these funds currently rely on fuzzy
  name matching (`app.calculations.find_fund`) or manual entry/correction on
  the review screen. A future improvement is a small, carefully-verified
  ticker↔CUSIP / ticker↔fund-name mapping for the highest-volume funds in
  each family -- deliberately left out of this initial build rather than
  guessed from memory (see the PIMCO note above).
- **PIMCO's state-by-state municipal bond tables** (source PDF pages 9-15)
  are not loaded at all -- only the U.S.-government-obligations table. Out
  of scope for this product's core calculation.

## Updating for a new tax year

1. Get each fund family's new year's tax-information PDF and drop it into
   `data/source_pdfs/` (keep the same file names, or update the `SRC`/
   `IN_FILE` path in the corresponding `parse_*.py`).
2. Regenerate each `*_raw.txt` (or, for Schwab, re-run the OCR commands
   above if the new PDF is also scanned/image-only -- check with
   `pdfimages -list` first, don't assume).
3. Re-run each `python data/parse_*.py` and spot-check the output CSV
   (row counts, a few known tickers/percentages, and that the CA/CT/NY
   column direction still matches that family's footnote wording).
4. Run `python scripts/seed_db.py` -- it's idempotent per `(family, ticker,
   fund_number, tax_year)`, so it's safe to re-run.
