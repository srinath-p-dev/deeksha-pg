from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.tenant import Tenant


class Settlement(Base):
    """Final deposit settlement when a tenant moves out.

    refund_amount = deposit_collected - pending_dues - total_deductions
    (negative means the tenant still owes money).
    """

    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), unique=True
    )
    move_out_date: Mapped[date] = mapped_column(Date)
    deposit_collected: Mapped[int] = mapped_column(Integer)
    pending_dues: Mapped[int] = mapped_column(Integer)
    total_deductions: Mapped[int] = mapped_column(Integer)
    refund_amount: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")
    settled_on: Mapped[date] = mapped_column(Date)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="settlement")
    deductions: Mapped[list["SettlementDeduction"]] = relationship(
        back_populates="settlement", cascade="all, delete-orphan", passive_deletes=True
    )


class SettlementDeduction(Base):
    __tablename__ = "settlement_deductions"

    id: Mapped[int] = mapped_column(primary_key=True)
    settlement_id: Mapped[int] = mapped_column(ForeignKey("settlements.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(200))
    amount: Mapped[int] = mapped_column(Integer)

    settlement: Mapped[Settlement] = relationship(back_populates="deductions")
