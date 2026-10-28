"""Queue WhatsApp messages. Nothing here talks to WhatsApp; the worker does that."""

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import MessageLog
from app.models.enums import MessageKind, MessageStatus
from app.services.app_settings import get_app_setting


def enqueue(
    db: Session,
    kind: MessageKind,
    recipient: str,
    body: str,
    *,
    dedupe_key: str | None = None,
    tenant_id: int | None = None,
    expires_at: datetime | None = None,
) -> bool:
    """Add a message to the outbox. Returns False if `dedupe_key` was already queued.

    Uses INSERT ... ON CONFLICT DO NOTHING so two concurrent runs can't both
    queue the same scheduled message. Joins the caller's transaction: the
    message is only queued if the caller's change commits.
    """
    stmt = (
        insert(MessageLog)
        .values(
            kind=kind,
            recipient=recipient,
            body=body,
            dedupe_key=dedupe_key,
            tenant_id=tenant_id,
            expires_at=expires_at,
            status=MessageStatus.pending,
            attempts=0,
            error="",
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(MessageLog.id)
    )
    # RETURNING gives back the new id, or nothing if the dedupe_key already existed
    return db.execute(stmt).scalar_one_or_none() is not None


def notify_owner(db: Session, body: str, kind: MessageKind = MessageKind.owner_change) -> bool:
    """Queue a WhatsApp message to the owner's number (if one is configured)."""
    number = get_app_setting(db, "owner_whatsapp")
    if not number:
        return False
    return enqueue(db, kind, number, body)
