from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from ..config import settings
from ..db import get_db
from ..limiter import limiter
from ..models import User
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Register(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field("", max_length=120)


class Login(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


@router.post("/register")
@limiter.limit("5/minute")
def register(request: Request, body: Register, db: Session = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(403, "Registration is disabled")
    if db.query(User).filter_by(email=body.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    u = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name)
    db.add(u); db.commit()
    return {"token": create_token(u.id), "user": {"id": u.id, "email": u.email, "full_name": u.full_name}}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, body: Login, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=body.email.lower()).first()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")  # same message for both cases
    return {"token": create_token(u.id), "user": {"id": u.id, "email": u.email, "full_name": u.full_name}}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name}
