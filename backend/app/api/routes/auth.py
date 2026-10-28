import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.core.timeutil import now_ist
from app.models import User, UserSession
from app.schemas import ChangePasswordIn, LoginIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple in-memory brute-force protection: max 10 failed logins per IP per 15 min.
_FAILS: dict[str, deque[float]] = defaultdict(deque)
_WINDOW, _MAX_FAILS = 15 * 60, 10


def _client_ip(request: Request) -> str:
    # Behind Caddy, the real client IP is in X-Forwarded-For
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "")


def _too_many_fails(ip: str) -> bool:
    fails = _FAILS[ip]
    while fails and fails[0] < time.monotonic() - _WINDOW:
        fails.popleft()
    return len(fails) >= _MAX_FAILS


@router.post("/login", response_model=UserOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    if _too_many_fails(ip):
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")

    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        _FAILS[ip].append(time.monotonic())
        raise HTTPException(401, "Wrong email or password")

    token = new_session_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=now_ist() + timedelta(days=settings.session_days),
            user_agent=request.headers.get("user-agent", "")[:300],
            ip=ip[:64],
        )
    )
    user.last_login_at = now_ist()
    db.commit()

    # httpOnly: JavaScript can't read it. SameSite=Lax: not sent on cross-site POSTs.
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is wrong")
    user.password_hash = hash_password(data.new_password)
    # Log out every other device
    current = hash_token(request.cookies.get(SESSION_COOKIE, ""))
    db.execute(
        delete(UserSession).where(UserSession.user_id == user.id, UserSession.token_hash != current)
    )
    db.commit()
