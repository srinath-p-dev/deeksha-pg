"""Building and queueing the scheduled WhatsApp messages."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutil import month_start
from app.messaging import templates
from app.messaging.outbox import enqueue
from app.models import Room, Tenant
from app.models.enums import OCCUPYING, MessageKind
from app.services.app_settings import get_app_setting, pg_name
from app.services.fmt import inr
from app.services.rent import generate_month, get_record, outstanding


def occupying_tenants(db: Session) -> list[Tenant]:
    return list(
        db.scalars(
            select(Tenant)
            .join(Room)
            .where(Tenant.status.in_(OCCUPYING))
            .order_by(Room.number, Tenant.name)
        ).all()
    )


def reminder_body(db: Session, tenant: Tenant, today: date) -> str | None:
    """The reminder text for a tenant, or None if they owe nothing."""
    dues = outstanding(db, tenant.id, up_to=today)
    deposit = tenant.deposit_balance
    if not dues and deposit == 0:
        return None
    return templates.rent_reminder(
        pg_name(db), tenant, dues, deposit, get_app_setting(db, "payment_note") or ""
    )


def queue_rent_reminders(db: Session, today: date, expires_at: datetime | None = None) -> int:
    """Queue today's reminder for every tenant who owes money. Safe to re-run.

    Unsent reminders expire at the cutoff time (default 9 PM) so nobody gets
    a rent reminder late at night after an outage.
    """
    generate_month(db, today)
    expires = expires_at or datetime.combine(today, settings.reminder_cutoff, tzinfo=settings.tz)
    queued = 0
    for tenant in occupying_tenants(db):
        body = reminder_body(db, tenant, today)
        if body and enqueue(
            db,
            MessageKind.rent_reminder,
            tenant.phone,
            body,
            dedupe_key=f"rent_reminder:{tenant.id}:{today.isoformat()}",
            tenant_id=tenant.id,
            expires_at=expires,
        ):
            queued += 1
    return queued


def unpaid_rows(db: Session, today: date) -> list[dict]:
    """Tenants who owe anything (rent up to this month, or deposit), for report + dashboard."""
    month = month_start(today)
    rows = []
    for tenant in occupying_tenants(db):
        dues = outstanding(db, tenant.id, up_to=month)
        rent_due = sum(d.balance for d in dues)
        deposit = tenant.deposit_balance
        if rent_due == 0 and deposit == 0:
            continue
        record = get_record(db, tenant.id, month)
        month_balance = record.balance if record else 0
        parts = []
        if record and month_balance > 0:
            parts.append("Partial" if record.amount_paid > 0 else "Unpaid")
        if rent_due - month_balance > 0:
            parts.append("older dues")
        if deposit > 0:
            parts.append(f"deposit {inr(deposit)}")
        rows.append(
            {
                "tenant_id": tenant.id,
                "name": tenant.name,
                "room": tenant.room.number,
                "phone": tenant.phone,
                "month_status": record.status.value if record else None,
                "month_balance": month_balance,
                "older_dues": rent_due - month_balance,
                "deposit_balance": deposit,
                "amount": rent_due + deposit,
                "label": ", ".join(parts),
            }
        )
    return rows


def queue_owner_report(db: Session, today: date) -> bool:
    owner = get_app_setting(db, "owner_whatsapp")
    if not owner:
        return False
    generate_month(db, today)
    body = templates.owner_report(month_start(today), today, unpaid_rows(db, today))
    return enqueue(
        db,
        MessageKind.owner_report,
        owner,
        body,
        dedupe_key=f"owner_report:{month_start(today).isoformat()}",
    )
