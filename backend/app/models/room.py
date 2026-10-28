from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class RoomCategory(Base):
    """A price group, e.g. 'Standard – balcony'. Each has a rent per sharing type."""

    __tablename__ = "room_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    max_sharing: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    rates: Mapped[list["CategoryRate"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="CategoryRate.sharing"
    )
    rooms: Mapped[list["Room"]] = relationship(back_populates="category")

    def rate_for(self, sharing: int) -> int | None:
        for rate in self.rates:
            if rate.sharing == sharing:
                return rate.monthly_rent
        return None


class CategoryRate(Base):
    __tablename__ = "category_rates"
    __table_args__ = (UniqueConstraint("category_id", "sharing"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("room_categories.id", ondelete="CASCADE"))
    sharing: Mapped[int] = mapped_column(Integer)  # 1 = single ... 5 = 5-sharing
    monthly_rent: Mapped[int | None] = mapped_column(Integer)  # None = no default, enter manually

    category: Mapped[RoomCategory] = relationship(back_populates="rates")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(10), unique=True)
    floor: Mapped[int] = mapped_column(Integer)
    category_id: Mapped[int] = mapped_column(ForeignKey("room_categories.id"))
    notes: Mapped[str] = mapped_column(String(300), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[RoomCategory] = relationship(back_populates="rooms")
    tenants: Mapped[list["Tenant"]] = relationship(back_populates="room")  # noqa: F821
