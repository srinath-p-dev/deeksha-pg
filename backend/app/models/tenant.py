from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import DocumentKind, TenantStatus
from app.models.room import Room


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Part 2: a tenant login links here. Unused for now.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(15), index=True)  # 91XXXXXXXXXX
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), index=True)
    sharing: Mapped[int] = mapped_column(Integer)
    rent_override: Mapped[int | None] = mapped_column(Integer)  # None = use category rate
    deposit_amount: Mapped[int] = mapped_column(Integer, default=0)
    deposit_collected: Mapped[int] = mapped_column(Integer, default=0)
    joining_date: Mapped[date] = mapped_column(Date)
    biometric_no: Mapped[str] = mapped_column(String(50), default="")
    office_address: Mapped[str] = mapped_column(Text, default="")
    permanent_address: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, native_enum=False, length=20), default=TenantStatus.active, index=True
    )
    notice_date: Mapped[date | None] = mapped_column(Date)
    move_out_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    room: Mapped[Room] = relationship(back_populates="tenants")
    documents: Mapped[list["TenantDocument"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    rent_records: Mapped[list["RentRecord"]] = relationship(  # noqa: F821
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RentRecord.month.desc()",
    )
    settlement: Mapped["Settlement | None"] = relationship(  # noqa: F821
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def default_rent(self) -> int | None:
        return self.room.category.rate_for(self.sharing)

    @property
    def rent(self) -> int | None:
        """Effective monthly rent: manual override if set, else the category rate."""
        return self.rent_override if self.rent_override is not None else self.default_rent

    @property
    def deposit_balance(self) -> int:
        return max(0, self.deposit_amount - self.deposit_collected)


class TenantDocument(Base):
    __tablename__ = "tenant_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    kind: Mapped[DocumentKind] = mapped_column(Enum(DocumentKind, native_enum=False, length=20))
    storage_key: Mapped[str] = mapped_column(String(300))
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="documents")
