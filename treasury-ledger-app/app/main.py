import os

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.database import Base, engine
from app.routes import auth_routes, dashboard, clients, upload

# Create tables on first run (SQLite, zero-config). Seeding the fund
# database is a separate explicit step: `python scripts/seed_db.py`.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Treasury Ledger")

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
