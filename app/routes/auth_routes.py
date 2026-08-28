from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse)
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    firm_name: str = Form(""),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    if not email or "@" not in email:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Enter a valid email address."})
    if len(password) < 8:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Password must be at least 8 characters."})

    user = User(email=email, hashed_password=hash_password(password), firm_name=firm_name.strip() or None)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse("register.html", {"request": request, "error": "An account with that email already exists."})

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Incorrect email or password."})

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
