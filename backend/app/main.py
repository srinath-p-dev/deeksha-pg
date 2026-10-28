import logging
from datetime import datetime

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes import auth, dashboard, messages, rent, rooms, site, tenants
from app.core.config import settings
from app.core.db import get_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# All API routes live under /api, so in production the reverse proxy can send
# /api/* to FastAPI and everything else to Next.js on the same domain.
app = FastAPI(
    title="PG Manager API",
    docs_url="/api/docs" if not settings.is_production else None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
)


@app.middleware("http")
async def check_origin(request: Request, call_next):
    """CSRF protection: state-changing requests must come from our own site.

    Browsers always send an Origin header on cross-site POST/PUT/DELETE, so a
    malicious page can't make a logged-in owner's browser change data here.
    """
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.origin_list:
            return JSONResponse(status_code=403, content={"detail": "Request origin not allowed"})
    return await call_next(request)


for module in (auth, dashboard, messages, rent, rooms, tenants):
    app.include_router(module.router)
app.include_router(site.staff)
app.include_router(site.public)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    """Liveness check: is the API up, and can it reach the database?"""
    now_ist = datetime.now(settings.tz).isoformat(timespec="seconds")
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable", "time_ist": now_ist},
        )
    return {"status": "ok", "database": "ok", "time_ist": now_ist}
