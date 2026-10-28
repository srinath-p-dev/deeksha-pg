from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import MessageKind, MessageStatus


class MessageLog(Base):
    """Outbox + log for every WhatsApp message.

    Rows are inserted as 'pending' in the same transaction as the change that
    caused them; the worker sends them one by one. `dedupe_key` is UNIQUE, so a
    scheduled message (e.g. 'rent_reminder:42:2026-11-05') can only ever be
    queued once, no matter how often the job runs.
    """

    __tablename__ = "message_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[MessageKind] = mapped_column(Enum(MessageKind, native_enum=False, length=30))
    recipient: Mapped[str] = mapped_column(String(15))
    body: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus, native_enum=False, length=20),
        default=MessageStatus.pending,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
