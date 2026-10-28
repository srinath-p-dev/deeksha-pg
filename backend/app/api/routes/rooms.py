from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_staff
from app.core.db import get_db
from app.models import CategoryRate, Room, RoomCategory, Tenant, User
from app.models.enums import OCCUPYING
from app.schemas import CategoryOut, CategoryUpdate, Occupant, RoomOut, RoomUpdate
from app.services import fmt
from app.services.audit import record_change

router = APIRouter(prefix="/api", tags=["rooms"], dependencies=[Depends(require_staff)])


def _room_out(room: Room) -> RoomOut:
    occupants = [t for t in room.tenants if t.status in OCCUPYING]
    max_sharing = room.category.max_sharing
    capacity = min([max_sharing, *(t.sharing for t in occupants)])
    return RoomOut(
        id=room.id,
        number=room.number,
        floor=room.floor,
        category_id=room.category_id,
        category_name=room.category.name,
        max_sharing=max_sharing,
        notes=room.notes,
        is_active=room.is_active,
        occupants=[
            Occupant(id=t.id, name=t.name, sharing=t.sharing, status=t.status) for t in occupants
        ],
        capacity_now=capacity,
    )


@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    rooms = db.scalars(
        select(Room)
        .options(selectinload(Room.tenants), selectinload(Room.category))
        .order_by(Room.floor, Room.number)
    ).all()
    return [_room_out(r) for r in rooms]


@router.patch("/rooms/{room_id}", response_model=RoomOut)
def update_room(
    room_id: int,
    data: RoomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    changes = []
    if data.category_id is not None and data.category_id != room.category_id:
        category = db.get(RoomCategory, data.category_id)
        if not category:
            raise HTTPException(404, "Category not found")
        changes.append(f"• Category: {room.category.name} → {category.name}")
        room.category = category
    if data.notes is not None:
        room.notes = data.notes
    if data.is_active is not None and data.is_active != room.is_active:
        changes.append(f"• {'Activated' if data.is_active else 'Deactivated'}")
        room.is_active = data.is_active
    if changes:
        record_change(
            db, user, "room", room.id, "update", f"🚪 *Room {room.number} updated*\n" + "\n".join(changes)
        )
    db.commit()
    return _room_out(room)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    categories = db.scalars(
        select(RoomCategory)
        .options(selectinload(RoomCategory.rates), selectinload(RoomCategory.rooms))
        .order_by(RoomCategory.sort_order)
    ).all()
    out = []
    for c in categories:
        item = CategoryOut.model_validate(c)
        item.room_count = len(c.rooms)
        out.append(item)
    return out


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    category = db.get(RoomCategory, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    lines = []
    if data.name is not None and data.name != category.name:
        lines.append(f"• Name: {category.name} → {data.name}")
        category.name = data.name
    if data.description is not None:
        category.description = data.description

    for rate_in in data.rates or []:
        if rate_in.sharing > category.max_sharing:
            raise HTTPException(400, f"{category.name} allows up to {category.max_sharing}-sharing")
        rate = next((r for r in category.rates if r.sharing == rate_in.sharing), None)
        old = rate.monthly_rent if rate else None
        if old == rate_in.monthly_rent:
            continue
        if not data.apply_to_existing and old is not None:
            # Lock current tenants on this rate at their old rent
            tenants = db.scalars(
                select(Tenant)
                .join(Room)
                .where(
                    Room.category_id == category.id,
                    Tenant.sharing == rate_in.sharing,
                    Tenant.rent_override.is_(None),
                    Tenant.status.in_(OCCUPYING),
                )
            ).all()
            for t in tenants:
                t.rent_override = old
            if tenants:
                lines.append(f"  ({len(tenants)} current tenant(s) kept at {fmt.inr(old)})")
        if rate:
            rate.monthly_rent = rate_in.monthly_rent
        else:
            category.rates.append(
                CategoryRate(sharing=rate_in.sharing, monthly_rent=rate_in.monthly_rent)
            )
        lines.append(
            f"• {fmt.sharing_label(rate_in.sharing)}: {fmt.inr(old)} → {fmt.inr(rate_in.monthly_rent)}"
        )

    if lines:
        record_change(
            db, user, "category", category.id, "update",
            f"💰 *Rates updated*: {category.name}\n" + "\n".join(lines),
        )
    db.commit()
    db.refresh(category)
    item = CategoryOut.model_validate(category)
    item.room_count = len(category.rooms)
    return item
