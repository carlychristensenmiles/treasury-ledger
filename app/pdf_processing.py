"""
PDF ingestion: turn an uploaded 1099-DIV / broker tax PDF into text, reading
scanned/image-only pages via OCR -- not just parsing an existing text layer.

Strategy per page:
  1. Try direct text extraction (PyMuPDF / fitz). Fast and exact when the PDF
     has a real text layer (e.g. a broker's natively-generated PDF).
  2. If a page yields little/no text (heuristic: fewer than MIN_TEXT_CHARS
     characters), treat it as a scanned image: rasterize that page to a
     bitmap at OCR_DPI and run Tesseract OCR on it.

This mirrors exactly what we hit for real: 4 of the 5 fund-family source PDFs
used to seed this app's database had a normal text layer, but Schwab's did
not -- it was a genuine scanned/rasterized document (verified with
`pdfimages -list`, one full-page image per page, no text layer at all) and
had to be OCR'd to read. A user's own 1099-DIV, especially a mailed/scanned
copy, is exactly as likely to need this path, which is why it's not optional.
"""
from dataclasses import dataclass, field
import io
import re

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

MIN_TEXT_CHARS = 40  # below this, a page is treated as image-only and OCR'd
OCR_DPI = 300


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    used_ocr: bool


@dataclass
class ExtractionResult:
    pages: list = field(default_factory=list)  # list[ExtractedPage]
    full_text: str = ""
    page_count: int = 0
    ocr_page_count: int = 0


def extract_text(pdf_bytes: bytes) -> ExtractionResult:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    ocr_count = 0

    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        used_ocr = False
        if len(text.strip()) < MIN_TEXT_CHARS:
            ocr_text = _ocr_page(page)
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text
                used_ocr = True
                ocr_count += 1
        pages.append(ExtractedPage(page_number=i + 1, text=text, used_ocr=used_ocr))

    doc.close()
    full_text = "\n".join(p.text for p in pages)
    return ExtractionResult(pages=pages, full_text=full_text, page_count=len(pages), ocr_page_count=ocr_count)


def _ocr_page(page: "fitz.Page") -> str:
    zoom = OCR_DPI / 72.0  # PDF points are 72 dpi; scale up for a sharper OCR image
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img)


# --- Holding extraction: find "<ticker> ... $<amount>" style lines --------

LEADING_TICKER_RE = re.compile(r"^([A-Z]{2,6})\b")
ANY_TICKER_RE = re.compile(r"\b([A-Z]{2,6})\b")
DOLLAR_AMOUNT_RE = re.compile(r"\$?\s*(\d[\d,]*\.\d{2})\b")

NOISE_TICKERS = {
    "THE", "AND", "FOR", "USD", "IRS", "SSN", "TIN", "FATCA", "OID", "TOTAL",
    "BOX", "CUSIP", "FORM", "DIV", "INC", "LLC", "ETF", "LLP", "PLC", "AMT",
}


@dataclass
class ExtractedHolding:
    ticker: str
    amount: float
    source_line: str


def extract_holding_candidates(text: str) -> list:
    """
    Heuristic pass over extracted 1099-DIV text: find lines that look like
    "<TICKER SYMBOL> ... $<dollar amount>" (the typical shape of a per-fund
    row in a broker's Box 1a detail section) and surface them as candidate
    holdings for the user to confirm/edit -- this never auto-commits without
    review, since OCR and heuristic ticker matching can both be wrong.
    """
    candidates = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # The dollar amount: take the LAST money-shaped number on the line
        # (detail listings put ticker/name/CUSIP first and the Box 1a amount
        # last; a CUSIP or account number earlier on the same line would
        # otherwise be misread as the amount if we took the first number).
        amount_matches = list(DOLLAR_AMOUNT_RE.finditer(line))
        if not amount_matches:
            continue
        amount_str = amount_matches[-1].group(1)
        try:
            amount = float(amount_str.replace(",", ""))
        except ValueError:
            continue
        if amount <= 0:
            continue

        # The ticker: prefer an all-caps token at the very start of the line
        # (the normal shape of a per-fund detail row), otherwise fall back to
        # the first all-caps token anywhere before the amount.
        m = LEADING_TICKER_RE.match(line)
        if not m:
            before_amount = line[:amount_matches[-1].start()]
            m = ANY_TICKER_RE.search(before_amount)
        if not m:
            continue
        ticker = m.group(1)
        if ticker in NOISE_TICKERS:
            continue

        candidates.append(ExtractedHolding(ticker=ticker, amount=amount, source_line=line))
    return candidates
