from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Client, Holding
from app.auth import require_user
from app.calculations import calculate_exempt_amount

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

CACTNY_STATES = {"CA", "CT", "NY"}


@router.get("/clients", response_class=HTMLResponse)
def list_clients(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    clients = db.query(Client).filter(Client.user_id == user.id).order_by(Client.name).all()
    return templates.TemplateResponse("clients.html", {"request": request, "user": user, "clients": clients, "error": None})


@router.post("/clients", response_class=HTMLResponse)
def create_client(
    request: Request,
    name: str = Form(...),
    state: str = Form(""),
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    name = name.strip()
    state = state.strip().upper()[:2] or None
    if not name:
        clients = db.query(Client).filter(Client.user_id == user.id).order_by(Client.name).all()
        return templates.TemplateResponse("clients.html", {"request": request, "user": user, "clients": clients, "error": "Client name is required."})

    client = Client(user_id=user.id, name=name, state=state)
    db.add(client)
    db.commit()
    return RedirectResponse(f"/clients/{client.id}", status_code=303)


def _state_mode_for(client: Client, override: str | None) -> str:
    if override in ("ALL", "CACTNY"):
        return override
    if client.state in CACTNY_STATES:
        return "CACTNY"
    return "ALL"


@router.get("/clients/{client_id}", response_class=HTMLResponse)
def client_detail(request: Request, client_id: int, state_mode: str | None = None, db: Session = Depends(get_db)):
    user = require_user(request, db)
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == user.id).first()
    if not client:
        return RedirectResponse("/clients", status_code=303)

    mode = _state_mode_for(client, state_mode)
    holdings = db.query(Holding).filter(Holding.client_id == client.id).order_by(Holding.created_at.desc()).all()

    rows = []
    total_dividends = 0.0
    total_exempt = 0.0
    for h in holdings:
        result = calculate_exempt_amount(h.ordinary_dividends, h.fund, state_mode=mode)
        total_dividends += h.ordinary_dividends
        total_exempt += result.exempt_amount
        rows.append({
            "holding": h,
            "fund": h.fund,
            "result": result,
        })

    return templates.TemplateResponse("client_detail.html", {
        "request": request,
        "user": user,
        "client": client,
        "rows": rows,
        "mode": mode,
        "total_dividends": total_dividends,
        "total_exempt": total_exempt,
        "cactny_states": sorted(CACTNY_STATES),
    })


@router.post("/clients/{client_id}/holdings", response_class=HTMLResponse)
def add_holding_manual(
    request: Request,
    client_id: int,
    ticker: str = Form(...),
    ordinary_dividends: float = Form(...),
    db: Session = Depends(get_db),
):
    from app.calculations import find_fund

    user = require_user(request, db)
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == user.id).first()
    if not client:
        return RedirectResponse("/clients", status_code=303)

    fund = find_fund(db, ticker=ticker)
    result = calculate_exempt_amount(ordinary_dividends, fund, state_mode="ALL")

    holding = Holding(
        client_id=client.id,
        upload_id=None,
        fund_id=fund.id if fund else None,
        ticker_raw=ticker.strip().upper(),
        name_raw=fund.name if fund else None,
        ordinary_dividends=ordinary_dividends,
        matched=result.matched,
        pct_used=result.pct_used,
        exempt_amount=result.exempt_amount,
        cactny_restricted=result.cactny_restricted,
    )
    db.add(holding)
    db.commit()
    return RedirectResponse(f"/clients/{client.id}", status_code=303)


@router.post("/clients/{client_id}/holdings/{holding_id}/delete")
def delete_holding(request: Request, client_id: int, holding_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    client = db.query(Client).filter(Client.id == client_id, Client.user_id == user.id).first()
    if not client:
        return RedirectResponse("/clients", status_code=303)
    holding = db.query(Holding).filter(Holding.id == holding_id, Holding.client_id == client.id).first()
    if holding:
        db.delete(holding)
        db.commit()
    return RedirectResponse(f"/clients/{client_id}", status_code=303)
