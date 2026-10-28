from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import hash_token
from app.core.timeutil import now_ist
from app.models import Tenant, User, UserSession

SESSION_COOKIE = "pg_session"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the logged-in user from the session cookie, or 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not logged in")
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_token(token), UserSession.expires_at > now_ist()
        )
    )
    if not session or not session.user.is_active:
        raise HTTPException(401, "Session expired, please log in again")
    return session.user


def require_staff(user: User = Depends(get_current_user)) -> User:
    """Owner or admin only. Part 2 tenant logins will get 403 here."""
    if not user.is_staff:
        raise HTTPException(403, "Not allowed")
    return user


def get_tenant_or_404(tenant_id: int, db: Session) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return tenant
