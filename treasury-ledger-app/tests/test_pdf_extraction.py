import fitz  # PyMuPDF

from app.pdf_processing import extract_text, extract_holding_candidates


def make_text_pdf(path, lines):
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 16
    doc.save(path)
    doc.close()


def test_extract_text_from_native_text_pdf(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    make_text_pdf(str(pdf_path), [
        "Form 1099-DIV Detail",
        "VUSXX  Vanguard Treasury Money Market  $1,000.00",
        "BND    Vanguard Total Bond Market ETF  $500.00",
    ])
    result = extract_text(pdf_path.read_bytes())
    assert result.page_count == 1
    assert result.ocr_page_count == 0  # real text layer, no OCR needed
    assert "VUSXX" in result.full_text
    assert "BND" in result.full_text


def test_extract_holding_candidates_matches_ticker_and_amount():
    text = "VUSXX  Vanguard Treasury Money Market  $1,000.00\nBND  Vanguard Total Bond Market ETF  $500.00\n"
    candidates = extract_holding_candidates(text)
    tickers = {c.ticker: c.amount for c in candidates}
    assert tickers.get("VUSXX") == 1000.00
    assert tickers.get("BND") == 500.00


def test_extract_holding_candidates_ignores_noise_words():
    text = "THE TOTAL for this account was $500.00 as reported to the IRS.\n"
    candidates = extract_holding_candidates(text)
    assert all(c.ticker not in {"THE", "TOTAL", "IRS"} for c in candidates)


def test_ocr_fallback_on_image_only_page(tmp_path):
    """
    Build a PDF page that has NO text layer at all (only a rendered image of
    text), the same situation we hit for real with the Schwab source PDF
    (verified via `pdfimages -list`: a full-page image, no text layer). The
    extractor must fall back to OCR and still recover the text.
    """
    # Render a normal text page to a bitmap, then build a brand-new PDF whose
    # only content is that bitmap -- i.e. an image-only "scanned" page.
    src = fitz.open()
    src_page = src.new_page()
    src_page.insert_text((72, 100), "SWRSX Schwab TIPS Index Fund $250.00", fontsize=14)
    pix = src_page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("png")
    src.close()

    scanned = fitz.open()
    page = scanned.new_page()
    rect = page.rect
    page.insert_image(rect, stream=img_bytes)
    pdf_path = tmp_path / "scanned.pdf"
    scanned.save(str(pdf_path))
    scanned.close()

    result = extract_text(pdf_path.read_bytes())
    assert result.ocr_page_count == 1
    assert "SWRSX" in result.full_text.upper()
