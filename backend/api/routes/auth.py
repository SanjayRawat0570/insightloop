from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Dict

from fastapi import APIRouter, HTTPException
from jose import jwt
from passlib.context import CryptContext

try:
    from backend.db.models import User
    from backend.db.mongo import create_user, find_user_by_email
except ModuleNotFoundError:
    from db.models import User
    from db.mongo import create_user, find_user_by_email

try:
    from backend.utils.logging_config import get_logger
except ModuleNotFoundError:
    from utils.logging_config import get_logger

router = APIRouter()
log = get_logger("auth")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(data: Dict) -> str:
    payload = dict(data)
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload["exp"] = expire
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/register")
async def register(body: Dict):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")

    existing = await find_user_by_email(email)
    if existing:
        log.warning("register rejected (duplicate) email=%s", email)
        raise HTTPException(status_code=409, detail="email already registered")

    user = User(email=email, hashed_password=_hash_password(password))
    await create_user(user)
    log.info("register ok email=%s user=%s", email, user.id)

    token = _create_token({"sub": user.id, "email": user.email})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "plan": user.plan}}


@router.post("/login")
async def login(body: Dict):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    user = await find_user_by_email(email)
    if not user or not _verify_password(password, user.hashed_password):
        log.warning("login failed email=%s", email)
        raise HTTPException(status_code=401, detail="invalid email or password")

    log.info("login ok email=%s user=%s", email, user.id)
    token = _create_token({"sub": user.id, "email": user.email})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "plan": user.plan}}
