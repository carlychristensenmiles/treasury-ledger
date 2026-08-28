"""
Parse Fidelity 2025 Supplementary Tax Information into a clean CSV.

Format per line (pdftotext -layout):
   <fund number>   <fund name>[*]   <cusip>   <pct>%

IMPORTANT ASTERISK CONVENTION (Fidelity is the OUTLIER):
  Fidelity's own footnote: "* did not meet the minimum investment ... required
  to exempt the distribution ... in California, Connecticut, and New York."
  So an asterisk on a Fidelity fund means it FAILS the CA/CT/NY 50% test
  (the opposite of every other fund family in this dataset, where an asterisk
  means the fund PASSES/meets the threshold). We normalize this at parse time:
  we store a single boolean column `meets_ca_ct_ny` with consistent meaning
  everywhere (True = qualifies for the CA/CT/NY pass-through), so downstream
  code never has to remember per-family asterisk semantics.
"""
import csv
import re

IN_FILE = "fidelity_raw.txt"
OUT_FILE = "funds_fidelity.csv"

# a data row looks like: fund_number (digits), then name, then cusip (9 alnum), then pct%
ROW_RE = re.compile(
    r"^\s*(\d{3,6})\s+(.+?)\s+([0-9A-Z]{9})\s+([\d.]+)%\s*$"
)

rows = []
skipped = []
with open(IN_FILE, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        m = ROW_RE.match(line)
        if not m:
            continue
        fund_number, name, cusip, pct = m.groups()
        name = name.strip()
        has_asterisk = "*" in name
        name_clean = name.replace("*", "").strip()
        # collapse whitespace and strip trailing footnote markers like numbers in parens? none observed.
        name_clean = re.sub(r"\s{2,}", " ", name_clean)
        pct_val = float(pct)
        if pct_val <= 0:
            continue
        # Fidelity asterisk means FAILS the threshold -> meets_ca_ct_ny is the inverse
        meets_ca_ct_ny = not has_asterisk
        rows.append({
            "family": "Fidelity",
            "ticker": "",  # Fidelity's tax doc does not publish tickers, only fund number + CUSIP
            "fund_number": fund_number,
            "cusip": cusip,
            "name": name_clean,
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

print(f"Parsed {len(rows)} Fidelity fund rows -> {OUT_FILE}")
# sanity: how many asterisked (fail) vs not
fails = sum(1 for r in rows if r["meets_ca_ct_ny"] == "0")
print(f"  {fails} marked as NOT meeting CA/CT/NY threshold (had asterisk in source)")
print(f"  {len(rows) - fails} marked as meeting CA/CT/NY threshold (no asterisk)")
