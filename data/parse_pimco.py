"""
Parse PIMCO 2025 "Income from U.S. Government Obligations" tables into a CSV.

PIMCO's tax document lists funds by NAME only (open-end funds, closed-end
funds, interval funds, exchange-traded funds, and Fixed Income SHares) -- it
does not publish trading ticker symbols in this table. We deliberately do
NOT guess/hardcode ticker symbols from general knowledge here: a wrong
ticker-to-fund mapping in a tax product is worse than no mapping, since it
would silently misapply another fund's percentage. PIMCO funds are seeded
with ticker="" and are matched in the app by fund name (fuzzy match) or by
manual lookup; a user/CPA can attach the correct ticker once confirmed
against their own PIMCO statement.

A "-" in either percentage column means 0% / not applicable; those funds are
omitted (consistent with how Schwab's doc explicitly states "funds not shown
had 0%").

Asterisk convention: PIMCO's own footnote: "* Fund passes quarterly 50%
U.S. Government holdings threshold" -- asterisk = MEETS the CA/CT/NY
threshold (same direction as Vanguard/iShares/Schwab; opposite of Fidelity).
"""
import csv
import re

IN_FILE = "pimco_raw.txt"
OUT_FILE = "funds_pimco.csv"

# Section header lines that start a new fund-family sub-table (name only, no ticker column)
SECTION_HEADERS = {
    "PIMCO Funds", "PIMCO Equity Series", "PIMCO Closed-End Funds",
    "PIMCO Interval Funds", "PIMCO Exchange-Traded Funds",
    "PIMCO Fixed Income SHares Funds",
}

START_MARKER = "2025 Income from U.S. Government Obligations"
END_MARKER = "2025 Foreign Tax Credit Information"  # marks the true end of the gov-obligations table region

# A data row: fund name, then a % (or '-') for govt securities, then a % (or '-') for corp DRD.
ROW_RE = re.compile(
    r"^\s*(.+?)\s{2,}([\d.]+%|-)\s+([\d.]+%|-)\s*$"
)

rows = []
in_table = False
with open(IN_FILE, encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    line = line.rstrip("\n")
    stripped = line.strip()
    if START_MARKER in stripped:
        in_table = True
        continue
    if END_MARKER in stripped:
        in_table = False
        continue
    if not in_table:
        continue
    if not stripped:
        continue
    if stripped in SECTION_HEADERS:
        continue
    if stripped.startswith("Percentage of income") or stripped.startswith("Government Securities") \
       or stripped.startswith("government securities") or "deduction %" in stripped:
        continue
    if stripped.startswith("2025 Income from") or stripped.startswith("2025 PIMCO") or re.match(r"^\d+$", stripped):
        continue
    if re.match(r"^\d+\s", stripped) and ("merged into" in stripped or "On " in stripped):
        continue  # footnote text
    if stripped.startswith("*") or stripped.startswith("Fund passes"):
        continue

    m = ROW_RE.match(line)
    if not m:
        continue
    name, govt_pct, drd_pct = m.groups()
    name = name.strip()
    # strip footnote superscript digits e.g. "Fund1" / "Fund2" trailing the name
    has_asterisk = name.endswith("*")
    name = name.rstrip("*").strip()
    name = re.sub(r"(\d)$", "", name).strip() if re.search(r"[a-zA-Z]\d$", name) else name
    if govt_pct == "-":
        continue
    pct_val = float(govt_pct.rstrip("%"))
    if pct_val <= 0:
        continue
    rows.append({
        "family": "PIMCO",
        "ticker": "",
        "fund_number": "",
        "cusip": "",
        "name": name,
        "pct_govt_obligations": f"{pct_val:.4f}",
        "meets_ca_ct_ny": "1" if has_asterisk else "0",
        "tax_year": "2025",
    })

with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "family", "ticker", "fund_number", "cusip", "name",
        "pct_govt_obligations", "meets_ca_ct_ny", "tax_year",
    ])
    writer.writeheader()
    writer.writerows(rows)

print(f"Parsed {len(rows)} PIMCO fund rows -> {OUT_FILE}")
qualifies = sum(1 for r in rows if r["meets_ca_ct_ny"] == "1")
print(f"  {qualifies} marked as meeting CA/CT/NY threshold (asterisk in source)")
