from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_staff
from app.core.db import get_db
from app.core.timeutil import month_label, month_start, parse_month, today_ist
from app.models import Payment, RentRecord, Room, Tenant, User
from app.models.enums import PaymentMode, RentStatus
from app.schemas import (
    MarkPaidIn,
    MonthRow,
    MonthView,
    PaymentIn,
    PaymentOut,
    RentRecordOut,
    RentRecordUpdate,
)
from app.services.audit import record_change
from app.services.fmt import inr
from app.services.rent import generate_month, refresh_record

router = APIRouter(prefix="/api", tags=["rent"], dependencies=[Depends(require_staff)])

MODE_LABELS = {"cash": "Cash", "upi": "UPI", "bank": "Bank transfer"}
STATUS_LABELS = {"paid": "Paid ✅", "partial": "Partial", "unpaid": "Unpaid"}


def _month_param(month: str | None) -> date:
    return parse_month(month) if month else month_start(today_ist())


@router.get("/rent", response_model=MonthView)
def month_view(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"), db: Session = Depends(get_db)
):
    m = _month_param(month)
    records = db.scalars(
        select(RentRecord)
        .join(Tenant)
        .join(Room)
        .options(joinedload(RentRecord.tenant).joinedload(Tenant.room))
        .where(RentRecord.month == m)
        .order_by(Room.number, Tenant.name)
    ).unique().all()
    counts = {s.value: 0 for s in RentStatus}
    for r in records:
        counts[r.status.value] += 1
    expected = sum(r.amount_due for r in records)
    collected = sum(min(r.amount_paid, r.amount_due) for r in records)
    return MonthView(
        month=m,
        expected=expected,
        collected=collected,
        pending=expected - collected,
        counts=counts,
        rows=[
            MonthRow(
                record=RentRecordOut.model_validate(r),
                tenant_name=r.tenant.name,
                tenant_status=r.tenant.status,
                room_number=r.tenant.room.number,
                phone=r.tenant.phone,
            )
            for r in records
        ],
    )


@router.post("/rent/generate")
def generate(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"), db: Session = Depends(get_db)
):
    """Create any missing rent records for a month (normally done automatically)."""
    created = generate_month(db, _month_param(month))
    db.commit()
    return {"created": created}


@router.patch("/rent-records/{record_id}", response_model=RentRecordOut)
def update_record(
    record_id: int,
    data: RentRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    record = db.get(RentRecord, record_id)
    if not record:
        raise HTTPException(404, "Rent record not found")
    if data.note is not None:
        record.note = data.note
    if data.amount_due is not None and data.amount_due != record.amount_due:
        old = record.amount_due
        record.amount_due = data.amount_due
        refresh_record(record)
        t = record.tenant
        record_change(
            db, user, "rent", record.id, "update",
            f"🧾 *Rent changed*: {t.name} (Room {t.room.number}) — {month_label(record.month)}\n"
            f"• Due {inr(old)} → {inr(data.amount_due)}",
        )
    db.commit()
    return record


def _get_record(db: Session, record_id: int) -> RentRecord:
    record = db.get(RentRecord, record_id)
    if not record:
        raise HTTPException(404, "Rent record not found")
    return record


def _add_payment(
    db: Session, record: RentRecord, user: User, amount: int, paid_on: date,
    mode: PaymentMode, reference: str = "", note: str = "",
) -> None:
    db.add(
        Payment(
            tenant_id=record.tenant_id,
            rent_record=record,
            amount=amount,
            paid_on=paid_on,
            mode=mode,
            reference=reference,
            note=note,
            recorded_by_id=user.id,
        )
    )
    refresh_record(record)
    t = record.tenant
    record_change(
        db, user, "payment", record.id, "payment",
        f"💵 *Payment recorded*: {t.name} (Room {t.room.number})\n"
        f"• {inr(amount)} via {MODE_LABELS[mode.value]} for {month_label(record.month)}\n"
        f"• Status: {STATUS_LABELS[record.status.value]}"
        + (f" — balance {inr(record.balance)}" if record.balance else ""),
    )


def _remove_payment(db: Session, payment: Payment, user: User) -> RentRecord:
    record = payment.rent_record
    record.payments.remove(payment)
    db.delete(payment)
    refresh_record(record)
    t = record.tenant
    record_change(
        db, user, "payment", record.id, "delete",
        f"↩️ *Payment removed*: {t.name} (Room {t.room.number}) — {inr(payment.amount)} "
        f"for {month_label(record.month)}\n• Balance now {inr(record.balance)}",
    )
    return record


@router.post("/payments", response_model=RentRecordOut, status_code=201)
def record_payment(
    data: PaymentIn, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    record = _get_record(db, data.rent_record_id)
    if data.amount > record.balance:
        raise HTTPException(
            400,
            f"Amount is more than the balance for {month_label(record.month)} ({inr(record.balance)}).",
        )
    _add_payment(db, record, user, data.amount, data.paid_on, data.mode, data.reference, data.note)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/payments/{payment_id}", response_model=RentRecordOut)
def delete_payment(
    payment_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    record = _remove_payment(db, payment, user)
    db.commit()
    db.refresh(record)
    return record


# ---------- checklist (one tick = paid in full) ----------

CHECKLIST_NOTE = "Marked paid from checklist"


@router.post("/rent-records/{record_id}/mark-paid", response_model=RentRecordOut)
def mark_paid(
    record_id: int, data: MarkPaidIn, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    """Record the remaining balance as one payment, so the month becomes Paid."""
    record = _get_record(db, record_id)
    if record.balance == 0:
        raise HTTPException(400, "Already fully paid.")
    _add_payment(db, record, user, record.balance, data.paid_on or today_ist(), data.mode, note=CHECKLIST_NOTE)
    db.commit()
    db.refresh(record)
    return record


@router.post("/rent-records/{record_id}/unmark-paid", response_model=RentRecordOut)
def unmark_paid(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    """Undo the latest checklist tick. Payments entered with details are left alone."""
    record = _get_record(db, record_id)
    ticks = [p for p in record.payments if p.note == CHECKLIST_NOTE]
    if not ticks:
        raise HTTPException(
            400, "This payment was entered on the tenant's page — remove it there if it's wrong."
        )
    record = _remove_payment(db, max(ticks, key=lambda p: p.id), user)
    db.commit()
    db.refresh(record)
    return record


@router.get("/tenants/{tenant_id}/payments", response_model=list[PaymentOut])
def tenant_payments(tenant_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(Payment).where(Payment.tenant_id == tenant_id).order_by(Payment.paid_on.desc())
    ).all()
