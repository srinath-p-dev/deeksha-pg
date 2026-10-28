"""Sends queued WhatsApp messages one at a time, with human-like random delays.

Delivery rules:
- A row is marked 'sending' and committed BEFORE the HTTP call. If the process
  dies mid-send, that row becomes 'unknown' on restart and is NOT retried
  automatically (a missed message is better than a double one). You can retry
  it from the dashboard.
- Retriable failures (WhatsApp disconnected) wait and retry up to MAX_ATTEMPTS.
- Rent reminders are rebuilt just before sending, and skipped if the tenant
  paid in the meantime.
"""

import logging
import random
import time
from datetime import timedelta

from sqlalchemy import func, select, update

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.timeutil import now_ist, today_ist
from app.messaging import whatsapp_client
from app.models import MessageLog, Tenant
from app.models.enums import OCCUPYING, MessageKind, MessageStatus
from app.services.reminders import reminder_body

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
RETRY_AFTER = timedelta(minutes=5)
MAX_RUN_SECONDS = 50 * 60  # stop a run before the next scheduled one would overlap much


def recover_stuck() -> None:
    """On startup: anything left 'sending' crashed mid-send -> 'unknown'."""
    with SessionLocal() as db:
        db.execute(
            update(MessageLog)
            .where(MessageLog.status == MessageStatus.sending)
            .values(status=MessageStatus.unknown, error="Worker restarted while sending")
        )
        db.commit()


def _sent_today(db) -> int:
    start = now_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(
        select(func.count()).where(
            MessageLog.status == MessageStatus.sent, MessageLog.sent_at >= start
        )
    )


def _next_message(db) -> MessageLog | None:
    now = now_ist()
    # Expire stale ones first
    db.execute(
        update(MessageLog)
        .where(
            MessageLog.status == MessageStatus.pending,
            MessageLog.expires_at.is_not(None),
            MessageLog.expires_at < now,
        )
        .values(status=MessageStatus.expired)
    )
    return db.scalar(
        select(MessageLog)
        .where(MessageLog.status == MessageStatus.pending, MessageLog.next_attempt_at <= now)
        .order_by(MessageLog.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def _prepare(db, msg: MessageLog) -> bool:
    """Final checks before sending. Returns False if the message should be skipped."""
    if msg.kind != MessageKind.rent_reminder:
        return True
    tenant = db.get(Tenant, msg.tenant_id) if msg.tenant_id else None
    if tenant is None or tenant.status not in OCCUPYING:
        msg.status, msg.error = MessageStatus.skipped, "Tenant no longer staying"
        return False
    body = reminder_body(db, tenant, today_ist())
    if body is None:
        msg.status, msg.error = MessageStatus.skipped, "Paid before sending"
        return False
    msg.body, msg.recipient = body, tenant.phone
    return True


def dispatch_pending() -> int:
    """Send pending messages until none are left. Returns how many were sent."""
    started, sent = time.monotonic(), 0
    while time.monotonic() - started < MAX_RUN_SECONDS:
        with SessionLocal() as db:
            if _sent_today(db) >= settings.wa_daily_limit:
                log.warning("Daily WhatsApp limit (%s) reached; pausing", settings.wa_daily_limit)
                return sent
            msg = _next_message(db)
            if msg is None:
                db.commit()
                return sent
            if not _prepare(db, msg):
                db.commit()
                continue
            msg.status = MessageStatus.sending
            msg.attempts += 1
            db.commit()  # committed before sending: see module docstring

            try:
                whatsapp_client.send_text(msg.recipient, msg.body)
            except whatsapp_client.WhatsAppError as e:
                log.warning("Send failed for message %s: %s", msg.id, e)
                msg.error = str(e)[:1000]
                if e.retriable and msg.attempts < MAX_ATTEMPTS:
                    msg.status = MessageStatus.pending
                    msg.next_attempt_at = now_ist() + RETRY_AFTER
                else:
                    msg.status = MessageStatus.failed
                db.commit()
                if e.retriable:
                    return sent  # WhatsApp is probably down; try again next run
                continue

            msg.status = MessageStatus.sent
            msg.sent_at = now_ist()
            msg.error = ""
            db.commit()
            sent += 1
            log.info("Sent message %s (%s) to %s", msg.id, msg.kind.value, msg.recipient)

        # Human-like pause between messages to reduce ban risk
        time.sleep(random.uniform(settings.wa_min_delay_seconds, settings.wa_max_delay_seconds))
    return sent
