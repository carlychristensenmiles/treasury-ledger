import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import Base, engine, SessionLocal
from app.routes import auth_routes, dashboard, clients, upload
from app.seed import seed_funds, funds_table_is_empty

logger = logging.getLogger("treasury_ledger")

# Create tables on first run (SQLite, zero-config).
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Treasury Ledger")


@app.on_event("startup")
def seed_fund_database_if_empty():
    """
    Auto-seed the Fund table from data/funds_*.csv on first boot against a
    fresh (empty) database file.

    This matters most on a platform like Fly.io: the database lives on a
    persistent volume that's created empty the first time the app deploys,
    and there's no separate one-off "release step" guaranteed to run against
    that same volume (Fly's release_command runs on a different machine that
    may not have the volume attached). Rather than requiring a manual
    `fly ssh console` + `python scripts/seed_db.py` step after every fresh
    deploy -- easy to forget, and the app would otherwise come up with an
    empty fund database and match nothing -- the app checks for this itself
    and seeds automatically. It's a no-op after the first boot (and safe to
    re-run manually via scripts/seed_db.py at any time; seed_funds() is
    idempotent either way).
    """
    db = SessionLocal()
    try:
        if funds_table_is_empty(db):
            logger.info("Fund table is empty -- seeding from data/funds_*.csv ...")
            summary = seed_funds(db)
            logger.info("Seeded %s fund rows for tax year(s) %s", summary["total"], summary["tax_years"])
    finally:
        db.close()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-before-real-deployment")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_routes.router)
app.include_router(dashboard.router)
app.include_router(clients.router)
app.include_router(upload.router)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
