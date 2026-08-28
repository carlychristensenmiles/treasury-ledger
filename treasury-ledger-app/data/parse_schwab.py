"""
Parse the Schwab 2025 Supplementary Tax Information U.S. Government
Obligations table.

The source PDF is a scanned/rasterized document (each page is a full-page
image, no text layer at all -- pdftotext returns nothing). We rasterized it
with pdftoppm and ran it through Tesseract OCR (see schwab_raw.txt). Because
OCR output on a table like this is small (~29 funds) but prone to per-row
character errors, we hand-verified and hand-transcribed each row against the
OCR text and the rendered page images rather than regex-parsing OCR noise,
to avoid a wrong digit silently corrupting a tax percentage.

Money-market funds are published as multiple share-class ticker symbols
separated by "/" for a single percentage (footnote: "Percentages apply to
all share classes.") -- we expand those into one row per ticker.

Asterisk convention: Schwab's own footnote says "Shareholders in CA, CT and
NY should note that only the funds denoted with an asterisk (*) meet the
minimum investment requirements of these states to permit the pass-through
of exempt income." So asterisk = MEETS the threshold (same direction as
Vanguard/iShares/PIMCO; opposite of Fidelity).
"""
import csv

# (name, tickers_or_single_string, pct, meets_ca_ct_ny)
# Verified against OCR text in schwab_raw.txt lines 17-71 and the source PDF images.
RAW = [
    ("Schwab Treasury Inflation Protected Securities Index Fund", "SWRSX", 100.00, True),
    ("Schwab U.S. Aggregate Bond Index Fund", "SWAGX", 44.06, False),
    ("Schwab Short-Term Bond Index Fund", "SWSBX", 67.97, True),
    ("Schwab MarketTrack Growth Portfolio", "SWHGX", 11.58, False),
    ("Schwab MarketTrack Balanced Portfolio", "SWBGX", 22.55, False),
    ("Schwab MarketTrack Conservative Portfolio", "SWCGX", 30.94, False),
    ("Schwab Balanced Fund", "SWOBX", 34.93, False),
    ("Schwab Target 2010 Fund", "SWBRX", 39.16, False),
    ("Schwab Target 2015 Fund", "SWGRX", 37.53, False),
    ("Schwab Target 2020 Fund", "SWCRX", 35.92, False),
    ("Schwab Target 2025 Fund", "SWHRX", 35.20, False),
    ("Schwab Target 2030 Fund", "SWDRX", 24.36, False),
    ("Schwab Target 2035 Fund", "SWIRX", 16.75, False),
    ("Schwab Target 2040 Fund", "SWERX", 12.18, False),
    ("Schwab Target 2045 Fund", "SWMRX", 8.64, False),
    ("Schwab Target 2050 Fund", "SWNRX", 5.63, False),
    ("Schwab Target 2055 Fund", "SWORX", 3.89, False),
    ("Schwab Target 2060 Fund", "SWPRX", 2.75, False),
    ("Schwab Target 2065 Fund", "SWQRX", 1.46, False),
    ("Schwab Monthly Income Fund—Target Payout", "SWJRX", 13.79, False),
    ("Schwab Monthly Income Fund—Flexible Payout", "SWKRX", 14.17, False),
    ("Schwab Monthly Income Fund—Income Payout", "SWLRX", 16.01, False),
    ("Schwab Target 2010 Index Fund", "SWYAX", 40.37, False),
    ("Schwab Target 2015 Index Fund", "SWYBX", 38.54, False),
    ("Schwab Target 2020 Index Fund", "SWYLX", 40.08, False),
    ("Schwab Target 2025 Index Fund", "SWYDX", 38.38, False),
    ("Schwab Target 2030 Index Fund", "SWYEX", 28.78, False),
    ("Schwab Target 2035 Index Fund", "SWYFX", 20.89, False),
    ("Schwab Target 2040 Index Fund", "SWYGX", 15.51, False),
    ("Schwab Target 2045 Index Fund", "SWYHX", 10.93, False),
    ("Schwab Target 2050 Index Fund", "SWYMX", 6.99, False),
    ("Schwab Target 2055 Index Fund", "SWYJX", 4.91, False),
    ("Schwab Target 2060 Index Fund", "SWYNX", 3.45, False),
    ("Schwab Target 2065 Index Fund", "SWYOX", 1.84, False),
    ("Schwab Government Money Fund", "SWGXX/SNVXX/SGUXX", 36.20, False),
    ("Schwab Retirement Government Money Fund", "SNRXX", 35.58, False),
    ("Schwab Treasury Obligations Money Fund", "SNOXX/SCOXX", 31.30, False),
    ("Schwab U.S. Treasury Money Fund", "SNSXX/SUTXX", 99.99, True),
    ("Schwab California Municipal Money Fund", "SWKXX/SCAXX", 73.95, True),  # source shows '*' + footnote 2: "applies to California residents" (subset of the CA/CT/NY note)
    ("Schwab AMT Tax-Free Money Fund", "SWWXX/SCTXX", 79.52, False),
    ("Schwab Municipal Money Fund", "SWTXX/SWOXX", 96.41, False),
    ("Schwab New York Municipal Money Fund", "SWYXX/SNYXX", 24.81, False),
    ("Schwab U.S. Aggregate Bond ETF", "SCHZ", 44.18, False),
    ("Schwab U.S. TIPS ETF", "SCHP", 100.00, True),
    ("Schwab Short-Term U.S. Treasury ETF", "SCHO", 100.00, True),
    ("Schwab Intermediate-Term U.S. Treasury ETF", "SCHR", 100.00, True),
    ("Schwab Long-Term U.S. Treasury ETF", "SCHQ", 100.00, True),
    ("Schwab Core Bond ETF", "SCCR", 14.69, False),
    ("Schwab Government Money Market ETF", "SGVT", 36.66, False),
]

OUT_FILE = "funds_schwab.csv"
records = []
for name, tickers, pct, meets in RAW:
    for ticker in tickers.split("/"):
        ticker = ticker.strip()
        records.append({
            "family": "Schwab",
            "ticker": ticker,
            "fund_number": "",
            "cusip": "",
            "name": name,
            "pct_govt_obligations": f"{pct:.4f}",
            "meets_ca_ct_ny": "1" if meets else "0",
            "tax_year": "2025",
        })

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "family", "ticker", "fund_number", "cusip", "name",
        "pct_govt_obligations", "meets_ca_ct_ny", "tax_year",
    ])
    writer.writeheader()
    writer.writerows(records)

print(f"Wrote {len(records)} Schwab fund/share-class rows -> {OUT_FILE}")
