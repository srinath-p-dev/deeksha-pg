import enum


class Role(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    tenant = "tenant"  # Part 2


class TenantStatus(str, enum.Enum):
    active = "active"
    on_notice = "on_notice"
    vacated = "vacated"


# Tenants in these states occupy a bed, owe rent and get reminders.
OCCUPYING = (TenantStatus.active, TenantStatus.on_notice)


class RentStatus(str, enum.Enum):
    unpaid = "unpaid"
    partial = "partial"
    paid = "paid"


class PaymentMode(str, enum.Enum):
    cash = "cash"
    upi = "upi"
    bank = "bank"


class DocumentKind(str, enum.Enum):
    id_proof = "id_proof"
    photo = "photo"
    other = "other"


class MessageKind(str, enum.Enum):
    rent_reminder = "rent_reminder"
    owner_report = "owner_report"
    owner_change = "owner_change"
    system = "system"


class MessageStatus(str, enum.Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    failed = "failed"
    unknown = "unknown"  # crashed mid-send; not retried automatically
    skipped = "skipped"  # no longer needed (e.g. rent paid before sending)
    expired = "expired"  # too late to send


class GalleryKind(str, enum.Enum):
    photo = "photo"
    video = "video"  # uploaded video file
    video_url = "video_url"  # YouTube or other embeddable link
