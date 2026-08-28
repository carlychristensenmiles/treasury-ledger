"""
Parse Vanguard 2025 U.S. government obligations income info into a clean CSV.

The source PDF renders the fund table as TWO side-by-side columns per page
(left block, right block), and fund names sometimes wrap onto a second line.
Naive pdftotext -layout merges the two columns onto shared text lines, which
scrambles which percentage belongs to which fund name. To avoid that risk on
a tax-sensitive dataset, we use pdfplumber word-level bounding boxes: cluster
words into the left-column vs right-column band by x-position, then within
each band reconstruct rows top-to-bottom using y-position, joining wrapped
fund-name lines until we hit a line ending in "<TICKER> <pct>%".
"""
import csv
import os
import re
import pdfplumber

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_pdfs", "vanguard_2025.pdf")
OUT_FILE = "funds_vanguard.csv"

TICKER_PCT_RE = re.compile(r"^([A-Z]{2,6})\s+([\d.]+)%$")
PCT_ONLY_RE = re.compile(r"^([\d.]+)%$")

def extract_rows_from_page(page):
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    if not words:
        return []
    # Find the two column x-bands by looking at the header row's "Ticker" occurrences,
    # but simpler & robust: cluster all word x0's into 2 groups via a midpoint split.
    xs = sorted(w["x0"] for w in words)
    page_width = page.width
    mid = page_width / 2.0

    left_words = [w for w in words if w["x0"] < mid]
    right_words = [w for w in words if w["x0"] >= mid]

    def words_to_lines(ws):
        # group by rounded 'top' (y) into lines
        lines = {}
        for w in ws:
            key = round(w["top"] / 3) * 3  # bucket to tolerate small jitter
            lines.setdefault(key, []).append(w)
        out = []
        for key in sorted(lines.keys()):
            line_words = sorted(lines[key], key=lambda w: w["x0"])
            text = " ".join(w["text"] for w in line_words)
            out.append((key, text, line_words))
        return out

    rows = []
    for band_words in (left_words, right_words):
        lines = words_to_lines(band_words)
        pending_name_parts = []  # only used before the first row is completed
        band_rows = []  # (name_parts_list, ticker, pct) — name_parts_list is mutable so we can append continuations
        for _, text, line_words in lines:
            text = text.strip()
            if not text:
                continue
            if text.startswith("Vanguard fund") or "Percentage of" in text or "ordinary" in text.lower() \
               or "dividends from" in text.lower() or text.strip() in ("U.S. government", "U.S. Government") \
               or ("U.S. government" in text and "obligations" in text and len(text) < 40):
                pending_name_parts = []  # a header fragment must never leak into a fund name
                continue
            # A data line ends with "<TICKER> <pct>%" as the last two tokens, but ticker
            # and pct might be split from the name by large whitespace already collapsed.
            # Try to match ticker+pct at the END of the line.
            m = re.search(r"([A-Z][A-Z0-9]{1,6})\s+([\d.]+)%\s*$", text)
            if m:
                ticker, pct = m.groups()
                name_part = text[:m.start()].strip()
                parts = list(pending_name_parts)
                parts.append(name_part)
                pending_name_parts = []
                band_rows.append([parts, ticker, pct])
            else:
                # Continuation of a wrapped fund name (no ticker/pct on this line).
                # Empirically (verified against source), a bare continuation line that
                # follows a completed row ALWAYS finishes that previous row's name
                # (e.g. "Cash Reserves Federal Money Market" + next-line "Fund Admiral*"
                # -> "Cash Reserves Federal Money Market Fund Admiral*"), not the next
                # fund's name. Only buffer as a prefix if no row has been completed yet
                # in this column band.
                if not text or PCT_ONLY_RE.match(text):
                    continue
                if band_rows:
                    band_rows[-1][0].append(text)
                else:
                    pending_name_parts.append(text)
        for parts, ticker, pct in band_rows:
            full_name = " ".join(p for p in parts if p).strip()
            full_name = re.sub(r"\s{2,}", " ", full_name)
            rows.append((full_name, ticker, pct))
    return rows


all_rows = []
with pdfplumber.open(SRC) as pdf:
    for i, page in enumerate(pdf.pages):
        if i == 0:
            continue  # cover/intro page, no table
        rows = extract_rows_from_page(page)
        all_rows.extend(rows)

# Clean + dedupe + build final records
seen = set()
records = []
for name, ticker, pct in all_rows:
    ticker = ticker.strip()
    name = name.strip().rstrip("*").strip()
    has_asterisk = False
    # asterisk may be attached to ticker or trail the name before ticker was stripped
    # re-check original name text for '*' before we stripped it above
    pass

# redo cleanly with asterisk detection preserved
records = []
for name, ticker, pct in all_rows:
    raw_name = name.strip()
    has_asterisk = "*" in raw_name or ticker.endswith("*")
    clean_name = raw_name.replace("*", "").strip()
    clean_ticker = ticker.replace("*", "").strip()
    pct_val = float(pct)
    if pct_val <= 0:
        continue
    if not re.match(r"^[A-Z]{2,6}$", clean_ticker):
        continue
    key = clean_ticker
    if key in seen:
        continue
    seen.add(key)
    records.append({
        "family": "Vanguard",
        "ticker": clean_ticker,
        "fund_number": "",
        "cusip": "",
        "name": clean_name,
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
    writer.writerows(records)

print(f"Parsed {len(records)} Vanguard fund rows -> {OUT_FILE}")
qualifies = sum(1 for r in records if r["meets_ca_ct_ny"] == "1")
print(f"  {qualifies} marked as meeting CA/CT/NY threshold (asterisk in source)")
