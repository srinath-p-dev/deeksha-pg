"""Pydantic schemas: the shapes of API requests and responses.

Request models validate input (types, lengths, phone format) before any route
code runs; FastAPI returns a 422 with details if validation fails.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.phone import normalize_phone
from app.models.enums import (
    DocumentKind,
    GalleryKind,
    MessageKind,
    MessageStatus,
    PaymentMode,
    RentStatus,
    Role,
    TenantStatus,
)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _phone(value: str | None) -> str | None:
    return normalize_phone(value) if value else value


# ---------- auth ----------


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORM):
    id: int
    name: str
    email: str | None
    role: Role


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


# ---------- rooms & rates ----------


class RateIn(BaseModel):
    sharing: int = Field(ge=1, le=10)
    monthly_rent: int | None = Field(default=None, ge=0)


class RateOut(ORM):
    sharing: int
    monthly_rent: int | None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)
    rates: list[RateIn] | None = None
    # False: tenants already on a changed rate keep paying the old rate (saved as custom rent)
    apply_to_existing: bool = False


class CategoryOut(ORM):
    id: int
    name: str
    description: str
    max_sharing: int
    sort_order: int
    rates: list[RateOut]
    room_count: int = 0


class Occupant(BaseModel):
    id: int
    name: str
    sharing: int
    status: TenantStatus


class RoomOut(BaseModel):
    id: int
    number: str
    floor: int
    category_id: int
    category_name: str
    max_sharing: int
    notes: str
    is_active: bool
    occupants: list[Occupant]
    capacity_now: int  # how many people the room can hold given current occupants' sharing


class RoomUpdate(BaseModel):
    category_id: int | None = None
    notes: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None


# ---------- tenants ----------


class TenantFields(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str
    room_id: int
    sharing: int = Field(ge=1, le=10)
    rent_override: int | None = Field(default=None, ge=0)
    deposit_amount: int = Field(default=0, ge=0)
    joining_date: date
    biometric_no: str = Field(default="", max_length=50)
    office_address: str = Field(default="", max_length=1000)
    permanent_address: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=2000)

    normalize_phone_field = field_validator("phone")(_phone)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required")
        return v


class TenantCreate(TenantFields):
    # None -> assume the full deposit was collected
    deposit_collected: int | None = Field(default=None, ge=0)
    # None -> prorated automatically from the joining date
    first_month_rent: int | None = Field(default=None, ge=0)


class TenantUpdate(BaseModel):
    """Only the fields you send are changed. Send rent_override: null to clear it."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = None
    room_id: int | None = None
    sharing: int | None = Field(default=None, ge=1, le=10)
    rent_override: int | None = Field(default=None, ge=0)
    deposit_amount: int | None = Field(default=None, ge=0)
    deposit_collected: int | None = Field(default=None, ge=0)
    joining_date: date | None = None
    biometric_no: str | None = Field(default=None, max_length=50)
    office_address: str | None = Field(default=None, max_length=1000)
    permanent_address: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    status: TenantStatus | None = None
    notice_date: date | None = None
    move_out_date: date | None = None
    # If rent changes: this month's due. None -> prorated automatically from today.
    current_month_due: int | None = Field(default=None, ge=0)

    normalize_phone_field = field_validator("phone")(_phone)


class DocumentOut(ORM):
    id: int
    kind: DocumentKind
    original_name: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime


class PaymentOut(ORM):
    id: int
    rent_record_id: int
    amount: int
    paid_on: date
    mode: PaymentMode
    reference: str
    note: str


class RentRecordOut(ORM):
    id: int
    tenant_id: int
    month: date
    amount_due: int
    amount_paid: int
    balance: int
    status: RentStatus
    note: str
    payments: list[PaymentOut] = []


class DeductionIn(BaseModel):
    reason: str = Field(min_length=1, max_length=200)
    amount: int = Field(ge=0)


class DeductionOut(ORM):
    reason: str
    amount: int


class SettlementIn(BaseModel):
    move_out_date: date
    deductions: list[DeductionIn] = []
    notes: str = Field(default="", max_length=2000)


class SettlementOut(ORM):
    move_out_date: date
    deposit_collected: int
    pending_dues: int
    total_deductions: int
    refund_amount: int
    notes: str
    settled_on: date
    deductions: list[DeductionOut]


class SettlementPreview(BaseModel):
    deposit_collected: int
    pending_dues: int
    dues_by_month: list[dict[str, Any]]


class TenantSummary(BaseModel):
    id: int
    name: str
    phone: str
    room_id: int
    room_number: str
    category_name: str
    sharing: int
    rent: int | None
    default_rent: int | None
    rent_override: int | None
    deposit_amount: int
    deposit_collected: int
    deposit_balance: int
    joining_date: date
    status: TenantStatus
    notice_date: date | None
    move_out_date: date | None
    outstanding: int
    current_month_status: RentStatus | None


class TenantDetail(TenantSummary):
    biometric_no: str
    office_address: str
    permanent_address: str
    notes: str
    created_at: datetime
    documents: list[DocumentOut]
    rent_records: list[RentRecordOut]
    settlement: SettlementOut | None


class NoticeIn(BaseModel):
    notice_date: date
    move_out_date: date | None = None


class RentRecordCreate(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    amount_due: int = Field(ge=0)
    note: str = ""


# ---------- rent & payments ----------


class RentRecordUpdate(BaseModel):
    amount_due: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class PaymentIn(BaseModel):
    rent_record_id: int
    amount: int = Field(gt=0)
    paid_on: date
    mode: PaymentMode
    reference: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=1000)


class MarkPaidIn(BaseModel):
    mode: PaymentMode = PaymentMode.cash
    paid_on: date | None = None  # None -> today


class MonthRow(BaseModel):
    record: RentRecordOut
    tenant_name: str
    tenant_status: TenantStatus
    room_number: str
    phone: str


class MonthView(BaseModel):
    month: date
    expected: int
    collected: int
    pending: int
    counts: dict[str, int]
    rows: list[MonthRow]


# ---------- messages ----------


class MessageOut(ORM):
    id: int
    kind: MessageKind
    recipient: str
    body: str
    status: MessageStatus
    attempts: int
    error: str
    tenant_id: int | None
    created_at: datetime
    sent_at: datetime | None


class AuditOut(ORM):
    id: int
    actor_name: str
    entity_type: str
    entity_id: int | None
    action: str
    summary: str
    created_at: datetime


# ---------- settings & site ----------


class AppSettingsIO(BaseModel):
    owner_whatsapp: str = ""
    payment_note: str = Field(default="", max_length=500)

    @field_validator("owner_whatsapp")
    @classmethod
    def _owner(cls, v: str) -> str:
        return normalize_phone(v) if v.strip() else ""


class SiteContent(BaseModel):
    pg_name: str = Field(max_length=100)
    tagline: str = Field(default="", max_length=200)
    about: str = Field(default="", max_length=5000)
    who_can_stay: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=500)
    maps_link: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=20)
    whatsapp: str = Field(default="", max_length=20)
    food: str = Field(default="", max_length=1000)
    amenities: list[str] = []
    rules: list[str] = []
    show_prices: bool = True

    @field_validator("whatsapp")
    @classmethod
    def _wa(cls, v: str) -> str:
        return normalize_phone(v) if v.strip() else ""


class GalleryOut(ORM):
    id: int
    kind: GalleryKind
    url: str | None
    caption: str
    sort_order: int
    media_url: str | None = None


class GalleryUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=200)
    sort_order: int | None = None


class GalleryLinkIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)
    caption: str = Field(default="", max_length=200)
