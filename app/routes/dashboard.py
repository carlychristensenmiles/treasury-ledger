from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Client, Upload, Holding
from app.auth import require_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)

    clients = db.query(Client).filter(Client.user_id == user.id).order_by(Client.name).all()
    recent_uploads = (
        db.query(Upload)
        .filter(Upload.user_id == user.id)
        .order_by(Upload.created_at.desc())
        .limit(8)
        .all()
    )

    totals = (
        db.query(
            func.coalesce(func.sum(Holding.ordinary_dividends), 0.0),
            func.coalesce(func.sum(Holding.exempt_amount), 0.0),
        )
        .join(Client, Holding.client_id == Client.id)
        .filter(Client.user_id == user.id)
        .first()
    )
    total_dividends, total_exempt = totals if totals else (0.0, 0.0)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "clients": clients,
        "recent_uploads": recent_uploads,
        "total_dividends": total_dividends,
        "total_exempt": total_exempt,
        "client_count": len(clients),
    })
