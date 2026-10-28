from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.core.db import get_db
from app.core.timeutil import end_of_day_ist, now_ist, today_ist
from app.messaging import whatsapp_client
from app.messaging.outbox import notify_owner
from app.models import AuditLog, MessageLog, User
from app.models.enums import MessageKind, MessageStatus
from app.schemas import AuditOut, MessageOut
from app.services.app_settings import get_app_setting
from app.services.audit import record_change
from app.services.reminders import queue_owner_report, queue_rent_reminders

router = APIRouter(prefix="/api", tags=["messages"], dependencies=[Depends(require_staff)])


@router.get("/messages", response_model=list[MessageOut])
def list_messages(
    status: MessageStatus | None = None,
    kind: MessageKind | None = None,
    tenant_id: int | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = select(MessageLog)
    if status:
        query = query.where(MessageLog.status == status)
    if kind:
        query = query.where(MessageLog.kind == kind)
    if tenant_id:
        query = query.where(MessageLog.tenant_id == tenant_id)
    return db.scalars(query.order_by(MessageLog.id.desc()).limit(limit).offset(offset)).all()


@router.post("/messages/{message_id}/retry", response_model=MessageOut)
def retry_message(message_id: int, db: Session = Depends(get_db)):
    msg = db.get(MessageLog, message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.status not in (MessageStatus.failed, MessageStatus.unknown, MessageStatus.expired):
        raise HTTPException(400, "Only failed, unknown or expired messages can be retried")
    msg.status = MessageStatus.pending
    msg.next_attempt_at = now_ist()
    msg.expires_at = None
    msg.error = ""
    db.commit()
    return msg


@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    return db.scalars(query.order_by(AuditLog.id.desc()).limit(limit)).all()


# ---------- WhatsApp connection ----------


@router.get("/whatsapp/status")
def whatsapp_status():
    status = whatsapp_client.get_status(timeout=4)
    if status is None:
        return {"reachable": False, "connected": False, "state": "unreachable", "qr": None, "me": None}
    return {"reachable": True, **status}


@router.post("/whatsapp/logout")
def whatsapp_logout(user: User = Depends(require_staff), db: Session = Depends(get_db)):
    if not whatsapp_client.logout():
        raise HTTPException(502, "WhatsApp service didn't respond")
    record_change(db, user, "whatsapp", None, "logout", "WhatsApp unlinked", notify=False)
    db.commit()
    return {"ok": True}


@router.post("/whatsapp/test")
def whatsapp_test(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    if not get_app_setting(db, "owner_whatsapp"):
        raise HTTPException(400, "Set the owner WhatsApp number in Settings first.")
    notify_owner(db, f"✅ Test message from the PG app (sent by {user.name}).", MessageKind.system)
    db.commit()
    return {"queued": True}


# ---------- manual job triggers ----------


@router.post("/jobs/reminders")
def run_reminders(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """Queue today's rent reminders now (each tenant still gets at most one per day)."""
    today = today_ist()
    queued = queue_rent_reminders(db, today, expires_at=end_of_day_ist(today))
    record_change(
        db, user, "job", None, "reminders", f"Rent reminders sent manually ({queued} queued)",
        notify=False,
    )
    db.commit()
    return {"queued": queued}


@router.post("/jobs/owner-report")
def run_owner_report(db: Session = Depends(get_db)):
    """Queue this month's unpaid report to the owner (once per month)."""
    if not get_app_setting(db, "owner_whatsapp"):
        raise HTTPException(400, "Set the owner WhatsApp number in Settings first.")
    queued = queue_owner_report(db, today_ist())
    db.commit()
    return {"queued": queued}
