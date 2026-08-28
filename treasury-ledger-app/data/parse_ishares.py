"""
Parse iShares/BlackRock 2025 U.S. Government Source Income table into a CSV.

Format (single column, pdftotext -layout works fine here):
   <TICKER>[**]   <Fund Name>   <pct>%

Asterisk convention: iShares uses "**" to mark a fund that MEETS the CA/CT/NY
50%-of-assets threshold (confirmed by the doc's own footnote near the table
header) -- this is the SAME direction as Vanguard/Schwab/PIMCO, and the
OPPOSITE of Fidelity's convention.
"""
import csv
import re

IN_FILE = "ishares_raw.txt"
OUT_FILE = "funds_ishares.csv"

ROW_RE = re.compile(
    r"^\s*([A-Z]{1,6})(\*{1,2})?\s+(.+?)\s+([\d.]+)%\s*$"
)

rows = []
with open(IN_FILE, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        m = ROW_RE.match(line)
        if not m:
            continue
        ticker, stars, name, pct = m.groups()
        name = re.sub(r"\s{2,}", " ", name.strip())
        pct_val = float(pct)
        if pct_val <= 0:
            continue
        meets_ca_ct_ny = bool(stars)  # ** = meets threshold
        rows.append({
            "family": "iShares",
            "ticker": ticker,
            "fund_number": "",
            "cusip": "",
            "name": name,
            "pct_govt_obligations": f"{pct_val:.4f}",
            "meets_ca_ct_ny": "1" if meets_ca_ct_ny else "0",
            "tax_year": "2025",
        })

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "family", "ticker", "fund_number", "cusip", "name",
        "pct_govt_obligations", "meets_ca_ct_ny", "tax_year",
    ])
    writer.writeheader()
    writer.writerows(rows)

print(f"Parsed {len(rows)} iShares fund rows -> {OUT_FILE}")
qualifies = sum(1 for r in rows if r["meets_ca_ct_ny"] == "1")
print(f"  {qualifies} marked as meeting CA/CT/NY threshold (** in source)")
