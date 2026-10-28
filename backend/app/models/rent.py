from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import PaymentMode, RentStatus
from app.models.tenant import Tenant


class RentRecord(Base):
    """What a tenant owes for one calendar month, and how much of it is paid."""

    __tablename__ = "rent_records"
    __table_args__ = (UniqueConstraint("tenant_id", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    month: Mapped[date] = mapped_column(Date, index=True)  # always the 1st of the month
    amount_due: Mapped[int] = mapped_column(Integer)
    amount_paid: Mapped[int] = mapped_column(Integer, default=0)  # kept in sync with payments
    status: Mapped[RentStatus] = mapped_column(
        Enum(RentStatus, native_enum=False, length=20), default=RentStatus.unpaid, index=True
    )
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="rent_records")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="rent_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Payment.paid_on",
    )

    @property
    def balance(self) -> int:
        return max(0, self.amount_due - self.amount_paid)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    rent_record_id: Mapped[int] = mapped_column(
        ForeignKey("rent_records.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    paid_on: Mapped[date] = mapped_column(Date)
    mode: Mapped[PaymentMode] = mapped_column(Enum(PaymentMode, native_enum=False, length=10))
    reference: Mapped[str] = mapped_column(String(100), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    recorded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rent_record: Mapped[RentRecord] = relationship(back_populates="payments")
