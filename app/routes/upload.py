import json

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Client, Upload, Holding
from app.auth import require_user
from app.pdf_processing import extract_text, extract_holding_candidates
from app.calculations import find_fund, calculate_exempt_amount

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    clients = db.query(Client).filter(Client.user_id == user.id).order_by(Client.name).all()
    return templates.TemplateResponse("upload.html", {"request": request, "user": user, "clients": clients, "error": None})


@router.post("/upload", response_class=HTMLResponse)
async def upload_submit(
    request: Request,
    client_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == user.id).first()
    if not client:
        clients = db.query(Client).filter(Client.user_id == user.id).order_by(Client.name).all()
        return templates.TemplateResponse("upload.html", {"request": request, "user": user, "clients": clients, "error": "Select a valid client."})

    pdf_bytes = await file.read()
    try:
        result = extract_text(pdf_bytes)
    except Exception as exc:  # a malformed/unsupported PDF shouldn't 500 the page
        clients = db.query(Client).filter(Client.user_id == user.id).order_by(Client.name).all()
        return templates.TemplateResponse("upload.html", {
            "request": request, "user": user, "clients": clients,
            "error": f"Could not read that PDF ({exc}). Try re-exporting or scanning it again.",
        })

    candidates = extract_holding_candidates(result.full_text)

    upload = Upload(
        user_id=user.id,
        client_id=client.id,
        filename=file.filename or "upload.pdf",
        status="processed",
        page_count=result.page_count,
        ocr_page_count=result.ocr_page_count,
        extracted_text_preview=result.full_text[:4000],
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    # Attach a best-guess fund match to each candidate for the review screen
    enriched = []
    for c in candidates:
        fund = find_fund(db, ticker=c.ticker)
        calc = calculate_exempt_amount(c.amount, fund, state_mode="ALL")
        enriched.append({
            "ticker": c.ticker,
            "amount": c.amount,
            "source_line": c.source_line,
            "fund": fund,
            "pct": calc.pct_used,
            "exempt_preview": calc.exempt_amount,
        })

    return templates.TemplateResponse("review.html", {
        "request": request,
        "user": user,
        "client": client,
        "upload": upload,
        "candidates": enriched,
        "ocr_page_count": result.ocr_page_count,
        "page_count": result.page_count,
    })


@router.post("/uploads/{upload_id}/confirm", response_class=HTMLResponse)
async def confirm_upload(
    request: Request,
    upload_id: int,
    db: Session = Depends(get_db),
):
    """
    Commits reviewed candidate rows into real Holding records. The review
    form posts one ticker[]/amount[]/include[] triple per candidate row so
    the user can edit or drop a row before anything is saved.
    """
    user = require_user(request, db)
    upload = db.query(Upload).filter(Upload.id == upload_id, Upload.user_id == user.id).first()
    if not upload:
        return RedirectResponse("/upload", status_code=303)

    form = await request.form()
    tickers = form.getlist("ticker")
    amounts = form.getlist("amount")
    includes = set(form.getlist("include"))  # values are row indices as strings

    saved = 0
    for i, (ticker, amount_str) in enumerate(zip(tickers, amounts)):
        if str(i) not in includes:
            continue
        ticker = ticker.strip().upper()
        if not ticker:
            continue
        try:
            amount = float(amount_str)
        except ValueError:
            continue
        if amount <= 0:
            continue

        fund = find_fund(db, ticker=ticker)
        calc = calculate_exempt_amount(amount, fund, state_mode="ALL")
        holding = Holding(
            upload_id=upload.id,
            client_id=upload.client_id,
            fund_id=fund.id if fund else None,
            ticker_raw=ticker,
            name_raw=fund.name if fund else None,
            ordinary_dividends=amount,
            matched=calc.matched,
            pct_used=calc.pct_used,
            exempt_amount=calc.exempt_amount,
            cactny_restricted=calc.cactny_restricted,
        )
        db.add(holding)
        saved += 1

    db.commit()
    return RedirectResponse(f"/clients/{upload.client_id}", status_code=303)
