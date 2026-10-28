from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_staff
from app.core.db import get_db
from app.core.timeutil import month_start, now_ist, today_ist
from app.messaging import whatsapp_client
from app.models import AuditLog, MessageLog, RentRecord, Room, Tenant
from app.models.enums import OCCUPYING, MessageStatus, TenantStatus
from app.schemas import AuditOut
from app.services.app_settings import SITE_DEFAULTS, get_app_setting, get_site_content
from app.services.reminders import unpaid_rows
from app.services.rent import generate_month

router = APIRouter(prefix="/api", tags=["dashboard"], dependencies=[Depends(require_staff)])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = today_ist()
    month = month_start(today)
    if generate_month(db, month):  # make sure this month's records exist
        db.commit()

    records = db.scalars(select(RentRecord).where(RentRecord.month == month)).all()
    expected = sum(r.amount_due for r in records)
    collected = sum(min(r.amount_paid, r.amount_due) for r in records)
    counts = {"paid": 0, "partial": 0, "unpaid": 0}
    for r in records:
        counts[r.status.value] += 1

    status_counts = dict(
        db.execute(select(Tenant.status, func.count()).group_by(Tenant.status)).all()
    )
    rooms = db.scalars(
        select(Room).options(selectinload(Room.tenants), selectinload(Room.category))
    ).all()
    occupied = empty = free_beds = 0
    for room in rooms:
        if not room.is_active:
            continue
        people = [t for t in room.tenants if t.status in OCCUPYING]
        capacity = min([room.category.max_sharing, *(t.sharing for t in people)])
        free_beds += max(0, capacity - len(people))
        if people:
            occupied += 1
        else:
            empty += 1

    on_notice = db.scalars(
        select(Tenant)
        .where(Tenant.status == TenantStatus.on_notice)
        .order_by(Tenant.move_out_date.nulls_last())
    ).all()
    deposit_pending = sum(
        t.deposit_balance
        for t in db.scalars(select(Tenant).where(Tenant.status.in_(OCCUPYING))).all()
    )

    week_ago = now_ist() - timedelta(days=7)
    msg_counts = dict(
        db.execute(
            select(MessageLog.status, func.count())
            .where(MessageLog.created_at >= week_ago)
            .group_by(MessageLog.status)
        ).all()
    )
    wa = whatsapp_client.get_status(timeout=3)
    recent = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(8)).all()
    site = get_site_content(db)

    return {
        "today": today,
        "month": month,
        "rent": {"expected": expected, "collected": collected, "pending": expected - collected, **counts},
        "unpaid": unpaid_rows(db, today),
        "tenants": {
            "active": status_counts.get(TenantStatus.active, 0),
            "on_notice": status_counts.get(TenantStatus.on_notice, 0),
            "vacated": status_counts.get(TenantStatus.vacated, 0),
        },
        "rooms": {"occupied": occupied, "empty": empty, "free_beds": free_beds},
        "deposit_pending": deposit_pending,
        "on_notice": [
            {
                "id": t.id,
                "name": t.name,
                "room": t.room.number,
                "move_out_date": t.move_out_date,
            }
            for t in on_notice
        ],
        "whatsapp": {
            "reachable": wa is not None,
            "connected": bool(wa and wa.get("connected")),
            "state": wa.get("state") if wa else "unreachable",
        },
        "owner_whatsapp_set": bool(get_app_setting(db, "owner_whatsapp")),
        "site_ready": bool(
            site["pg_name"] != SITE_DEFAULTS["pg_name"] and site["address"] and site["phone"]
        ),
        "messages_7d": {
            "sent": msg_counts.get(MessageStatus.sent, 0),
            "pending": msg_counts.get(MessageStatus.pending, 0),
            "failed": msg_counts.get(MessageStatus.failed, 0) + msg_counts.get(MessageStatus.unknown, 0),
        },
        "recent_activity": [AuditOut.model_validate(a) for a in recent],
    }
