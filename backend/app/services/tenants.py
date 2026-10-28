"""Tenant business logic. Routes stay thin and call these functions."""

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.core.timeutil import month_start, today_ist
from app.models import Room, Settlement, SettlementDeduction, Tenant, User
from app.models.enums import OCCUPYING, TenantStatus
from app.schemas import (
    SettlementIn,
    TenantCreate,
    TenantDetail,
    TenantSummary,
    TenantUpdate,
)
from app.services import fmt
from app.services.audit import record_change
from app.services.rent import (
    RentError,
    adjust_for_rent_change,
    ensure_record,
    get_record,
    outstanding,
    refresh_record,
    require_rent,
    total_outstanding,
)

# ---------- serialisation ----------


def to_summary(db: Session, t: Tenant) -> TenantSummary:
    record = get_record(db, t.id, month_start(today_ist()))
    return TenantSummary(
        id=t.id,
        name=t.name,
        phone=t.phone,
        room_id=t.room_id,
        room_number=t.room.number,
        category_name=t.room.category.name,
        sharing=t.sharing,
        rent=t.rent,
        default_rent=t.default_rent,
        rent_override=t.rent_override,
        deposit_amount=t.deposit_amount,
        deposit_collected=t.deposit_collected,
        deposit_balance=t.deposit_balance,
        joining_date=t.joining_date,
        status=t.status,
        notice_date=t.notice_date,
        move_out_date=t.move_out_date,
        outstanding=total_outstanding(db, t.id),
        current_month_status=record.status if record else None,
    )


def to_detail(db: Session, t: Tenant) -> TenantDetail:
    return TenantDetail(
        **to_summary(db, t).model_dump(),
        biometric_no=t.biometric_no,
        office_address=t.office_address,
        permanent_address=t.permanent_address,
        notes=t.notes,
        created_at=t.created_at,
        documents=t.documents,
        rent_records=t.rent_records,
        settlement=t.settlement,
    )


# ---------- validation ----------


def get_room(db: Session, room_id: int) -> Room:
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    return room


def check_capacity(db: Session, room: Room, sharing: int, exclude_tenant_id: int | None = None):
    """Refuse placements that overfill a room.

    A room holds at most its category's max sharing, and never more people
    than the smallest sharing type among its occupants (a Double-sharing tenant
    shares with at most one other person).
    """
    max_sharing = room.category.max_sharing
    if sharing > max_sharing:
        raise HTTPException(
            400, f"Room {room.number} ({room.category.name}) allows up to {max_sharing}-sharing."
        )
    if not room.is_active:
        raise HTTPException(400, f"Room {room.number} is marked inactive.")
    occupants = [
        t
        for t in room.tenants
        if t.status in OCCUPYING and t.id != exclude_tenant_id
    ]
    count = len(occupants) + 1
    if count > max_sharing:
        raise HTTPException(400, f"Room {room.number} is full ({len(occupants)} occupants).")
    tightest = min([sharing, *(o.sharing for o in occupants)])
    if count > tightest:
        who = "this tenant" if tightest == sharing else next(
            o.name for o in occupants if o.sharing == tightest
        )
        names = ", ".join(o.name for o in occupants) or "nobody"
        raise HTTPException(
            400,
            f"Room {room.number} would have {count} people, but {who} is on "
            f"{fmt.sharing_label(tightest)} sharing (current occupants: {names}).",
        )


def _rent_or_400(tenant: Tenant) -> int:
    try:
        return require_rent(tenant)
    except RentError as e:
        raise HTTPException(400, str(e)) from e


# ---------- create / update / delete ----------


def create_tenant(db: Session, data: TenantCreate, actor: User) -> Tenant:
    room = get_room(db, data.room_id)
    check_capacity(db, room, data.sharing)

    fields = data.model_dump(exclude={"first_month_rent", "deposit_collected"})
    tenant = Tenant(**fields, room=room)
    tenant.deposit_collected = (
        data.deposit_collected if data.deposit_collected is not None else data.deposit_amount
    )
    if tenant.deposit_collected > tenant.deposit_amount:
        raise HTTPException(400, "Deposit collected can't exceed the deposit amount.")
    db.add(tenant)
    db.flush()
    rent = _rent_or_400(tenant)

    # First rent record: the joining month if it's this month (prorated unless
    # given), otherwise the current month at full rent. Older months for
    # long-time tenants can be added by hand.
    this_month = month_start(today_ist())
    if month_start(tenant.joining_date) <= this_month:
        joined_now = month_start(tenant.joining_date) == this_month
        ensure_record(
            db, tenant, this_month, data.first_month_rent if joined_now else None
        )

    lines = [
        f"🆕 *New tenant*: {tenant.name}",
        f"• Room {room.number}, {fmt.sharing_label(tenant.sharing)} sharing",
        f"• Rent {fmt.inr(rent)}{' (custom)' if tenant.rent_override is not None else ''}",
        f"• Deposit {fmt.inr(tenant.deposit_amount)}"
        + (
            f" (collected {fmt.inr(tenant.deposit_collected)})"
            if tenant.deposit_balance
            else ""
        ),
        f"• Joining {fmt.fdate(tenant.joining_date)}",
        f"• Phone {fmt.phone(tenant.phone)}",
    ]
    record_change(db, actor, "tenant", tenant.id, "create", "\n".join(lines))
    return tenant


# Fields shown in change messages: (label, formatter)
_LABELS = {
    "name": ("Name", str),
    "phone": ("Phone", fmt.phone),
    "room": ("Room", str),
    "sharing": ("Sharing", fmt.sharing_label),
    "rent": ("Rent", fmt.inr),
    "deposit_amount": ("Deposit", fmt.inr),
    "deposit_collected": ("Deposit collected", fmt.inr),
    "joining_date": ("Joining date", fmt.fdate),
    "biometric_no": ("Biometric no.", lambda v: v or "—"),
    "status": ("Status", fmt.status_label),
    "notice_date": ("Notice date", fmt.fdate),
    "move_out_date": ("Move-out date", fmt.fdate),
}
_TEXT_FIELDS = {"office_address": "Office address", "permanent_address": "Permanent address", "notes": "Notes"}


def _snapshot(t: Tenant) -> dict:
    return {
        "name": t.name,
        "phone": t.phone,
        "room": t.room.number,
        "sharing": t.sharing,
        "rent": t.rent,
        "rent_override": t.rent_override,
        "deposit_amount": t.deposit_amount,
        "deposit_collected": t.deposit_collected,
        "joining_date": t.joining_date,
        "biometric_no": t.biometric_no,
        "status": t.status.value,
        "notice_date": t.notice_date,
        "move_out_date": t.move_out_date,
        "office_address": t.office_address,
        "permanent_address": t.permanent_address,
        "notes": t.notes,
    }


def _describe(before: dict, after: dict) -> tuple[list[str], dict]:
    lines, changes = [], {}
    for key, (label, f) in _LABELS.items():
        if before[key] != after[key]:
            old, new = f(before[key]), f(after[key])
            if key == "rent":
                if before["rent_override"] is not None:
                    old += " (custom)"
                if after["rent_override"] is not None:
                    new += " (custom)"
            lines.append(f"• {label}: {old} → {new}")
            changes[key] = [str(before[key]), str(after[key])]
    for k, label in _TEXT_FIELDS.items():
        if before[k] != after[k]:
            lines.append(f"• {label} updated")
            changes[k] = [before[k], after[k]]
    if before["rent"] == after["rent"] and before["rent_override"] != after["rent_override"]:
        lines.append("• Rent marked as " + ("custom" if after["rent_override"] is not None else "default"))
        changes["rent_override"] = [before["rent_override"], after["rent_override"]]
    return lines, changes


def update_tenant(db: Session, tenant: Tenant, data: TenantUpdate, actor: User) -> Tenant:
    values = data.model_dump(exclude_unset=True)
    current_month_due = values.pop("current_month_due", None)
    if values.get("status") == TenantStatus.vacated:
        raise HTTPException(400, "Use 'Move out & settle' to mark a tenant as vacated.")

    before = _snapshot(tenant)
    old_rent = tenant.rent
    was_occupying = tenant.status in OCCUPYING

    for key, value in values.items():
        if key == "room_id":
            tenant.room = get_room(db, value)
        setattr(tenant, key, value)

    if tenant.deposit_collected > tenant.deposit_amount:
        raise HTTPException(400, "Deposit collected can't exceed the deposit amount.")

    placement_changed = {"room_id", "sharing"} & values.keys() or (
        not was_occupying and tenant.status in OCCUPYING
    )
    if placement_changed and tenant.status in OCCUPYING:
        check_capacity(db, tenant.room, tenant.sharing, exclude_tenant_id=tenant.id)

    if tenant.status in OCCUPYING:
        new_rent = _rent_or_400(tenant)
        record = get_record(db, tenant.id, month_start(today_ist()))
        if record and current_month_due is not None:
            record.amount_due = current_month_due
            refresh_record(record)
        elif new_rent != old_rent:
            adjust_for_rent_change(db, tenant, old_rent, new_rent, today_ist())

    db.flush()
    after = _snapshot(tenant)
    lines, changes = _describe(before, after)
    if current_month_due is not None:
        lines.append(f"• This month's due set to {fmt.inr(current_month_due)}")
    if lines:
        summary = f"✏️ *Tenant updated*: {tenant.name} (Room {tenant.room.number})\n" + "\n".join(lines)
        record_change(db, actor, "tenant", tenant.id, "update", summary, changes)
    return tenant


def give_notice(db: Session, tenant: Tenant, notice_date: date, move_out: date | None, actor: User):
    if tenant.status == TenantStatus.vacated:
        raise HTTPException(400, "Tenant has already vacated.")
    tenant.status = TenantStatus.on_notice
    tenant.notice_date = notice_date
    tenant.move_out_date = move_out
    record_change(
        db,
        actor,
        "tenant",
        tenant.id,
        "notice",
        f"📤 *Notice given*: {tenant.name} (Room {tenant.room.number})\n"
        f"• Notice date {fmt.fdate(notice_date)}\n"
        f"• Moving out {fmt.fdate(move_out)}",
    )


def delete_tenant(db: Session, tenant: Tenant, actor: User) -> None:
    keys = [d.storage_key for d in tenant.documents]
    summary = (
        f"🗑️ *Tenant deleted permanently*: {tenant.name} (Room {tenant.room.number}, "
        f"{fmt.phone(tenant.phone)})\n• All rent history and documents removed"
    )
    tenant_id = tenant.id
    db.delete(tenant)
    record_change(db, actor, "tenant", tenant_id, "delete", summary)
    db.flush()
    for key in keys:  # files are removed only after the DB delete succeeded
        storage.delete(key)


# ---------- move-out settlement ----------


def settlement_preview(db: Session, tenant: Tenant) -> dict:
    dues = outstanding(db, tenant.id)
    return {
        "deposit_collected": tenant.deposit_collected,
        "pending_dues": sum(d.balance for d in dues),
        "dues_by_month": [{"month": d.month, "balance": d.balance} for d in dues],
    }


def settle(db: Session, tenant: Tenant, data: SettlementIn, actor: User) -> Settlement:
    if tenant.settlement:
        raise HTTPException(400, "This tenant has already been settled.")
    preview = settlement_preview(db, tenant)
    deductions = sum(d.amount for d in data.deductions)
    settlement = Settlement(
        tenant=tenant,
        move_out_date=data.move_out_date,
        deposit_collected=preview["deposit_collected"],
        pending_dues=preview["pending_dues"],
        total_deductions=deductions,
        refund_amount=preview["deposit_collected"] - preview["pending_dues"] - deductions,
        notes=data.notes,
        settled_on=today_ist(),
        created_by_id=actor.id,
        deductions=[SettlementDeduction(reason=d.reason, amount=d.amount) for d in data.deductions],
    )
    db.add(settlement)
    tenant.status = TenantStatus.vacated
    tenant.move_out_date = data.move_out_date

    lines = [
        f"🏁 *Tenant vacated & settled*: {tenant.name} (Room {tenant.room.number})",
        f"• Move-out {fmt.fdate(data.move_out_date)}",
        f"• Deposit collected {fmt.inr(settlement.deposit_collected)}",
        f"• Pending dues −{fmt.inr(settlement.pending_dues)}",
    ]
    lines += [f"• {d.reason} −{fmt.inr(d.amount)}" for d in data.deductions]
    refund = settlement.refund_amount
    lines.append(
        f"• *Refund {fmt.inr(refund)}*" if refund >= 0 else f"• *Tenant owes {fmt.inr(-refund)}*"
    )
    record_change(db, actor, "tenant", tenant.id, "vacate", "\n".join(lines))
    return settlement


def list_tenants(db: Session, status: str | None, q: str | None) -> list[Tenant]:
    query = select(Tenant).join(Room)
    if status == "current":
        query = query.where(Tenant.status.in_(OCCUPYING))
    elif status:
        query = query.where(Tenant.status == TenantStatus(status))
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            Tenant.name.ilike(like) | Tenant.phone.ilike(like) | Room.number.ilike(like)
        )
    return list(db.scalars(query.order_by(Room.number, Tenant.name)).all())
