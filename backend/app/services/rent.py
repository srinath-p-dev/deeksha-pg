"""Rent rules: monthly records, proration, payment status, outstanding dues."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import month_end, month_start, prorate, remaining_days, days_in_month
from app.models import RentRecord, Tenant
from app.models.enums import OCCUPYING, RentStatus


class RentError(ValueError):
    pass


def compute_status(amount_due: int, amount_paid: int) -> RentStatus:
    if amount_paid >= amount_due:
        return RentStatus.paid
    if amount_paid > 0:
        return RentStatus.partial
    return RentStatus.unpaid


def refresh_record(record: RentRecord) -> None:
    """Recalculate amount_paid and status from the record's payments."""
    record.amount_paid = sum(p.amount for p in record.payments)
    record.status = compute_status(record.amount_due, record.amount_paid)


def require_rent(tenant: Tenant) -> int:
    rent = tenant.rent
    if rent is None:
        raise RentError(
            f"No default rent is set for '{tenant.room.category.name}' with "
            f"{tenant.sharing}-sharing. Set it under Rates, or enter a custom rent."
        )
    return rent


def first_month_amount(rent: int, joining_date: date, month: date) -> int:
    """Prorated rent if the tenant joined during `month`, else the full rent."""
    if month_start(joining_date) == month:
        return prorate(rent, joining_date)
    return rent


def get_record(db: Session, tenant_id: int, month: date) -> RentRecord | None:
    return db.scalar(
        select(RentRecord).where(RentRecord.tenant_id == tenant_id, RentRecord.month == month)
    )


def ensure_record(
    db: Session, tenant: Tenant, month: date, amount: int | None = None
) -> RentRecord | None:
    """Create the tenant's record for `month` if missing. Idempotent.

    Returns None if the tenant hadn't joined by that month or has no rent set.
    """
    month = month_start(month)
    existing = get_record(db, tenant.id, month)
    if existing:
        return existing
    if tenant.joining_date > month_end(month):
        return None
    if amount is None:
        if tenant.rent is None:
            return None
        amount = first_month_amount(tenant.rent, tenant.joining_date, month)
    record = RentRecord(
        tenant_id=tenant.id,
        month=month,
        amount_due=amount,
        amount_paid=0,
        status=compute_status(amount, 0),
    )
    db.add(record)
    db.flush()
    return record


def generate_month(db: Session, month: date) -> int:
    """Create missing records for every occupying tenant for `month`. Safe to re-run."""
    month = month_start(month)
    tenants = db.scalars(
        select(Tenant).where(Tenant.status.in_(OCCUPYING), Tenant.joining_date <= month_end(month))
    ).all()
    created = 0
    for tenant in tenants:
        if tenant.move_out_date and tenant.move_out_date < month:
            continue
        if get_record(db, tenant.id, month) is None and ensure_record(db, tenant, month):
            created += 1
    return created


def adjust_for_rent_change(
    db: Session, tenant: Tenant, old_rent: int | None, new_rent: int, change_date: date
) -> RentRecord | None:
    """Prorate the current month after a mid-month rent change.

    Days before `change_date` stay at the old rent; days from it on use the new
    rent. Works incrementally, so several changes in one month add up correctly.
    """
    record = get_record(db, tenant.id, month_start(change_date))
    if record is None or old_rent is None or old_rent == new_rent:
        return record
    days = remaining_days(change_date)
    delta = round((new_rent - old_rent) * days / days_in_month(change_date))
    record.amount_due = max(0, record.amount_due + delta)
    refresh_record(record)
    return record


@dataclass
class Due:
    month: date
    balance: int


def outstanding(db: Session, tenant_id: int, up_to: date | None = None) -> list[Due]:
    """Unpaid balances per month (oldest first), optionally up to a month."""
    query = select(RentRecord).where(
        RentRecord.tenant_id == tenant_id, RentRecord.status != RentStatus.paid
    )
    if up_to:
        query = query.where(RentRecord.month <= month_start(up_to))
    records = db.scalars(query.order_by(RentRecord.month)).all()
    return [Due(r.month, r.balance) for r in records if r.balance > 0]


def total_outstanding(db: Session, tenant_id: int, up_to: date | None = None) -> int:
    return sum(d.balance for d in outstanding(db, tenant_id, up_to))
