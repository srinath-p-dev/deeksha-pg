"""Human-readable formatting for WhatsApp messages and audit summaries."""

from datetime import date

from app.core.phone import display_phone

SHARING_LABELS = {1: "Single", 2: "Double", 3: "Triple"}

STATUS_LABELS = {"active": "Active", "on_notice": "On notice", "vacated": "Vacated"}


def inr(amount: int | None) -> str:
    """6000 -> '₹6,000'; 150000 -> '₹1,50,000' (Indian digit grouping)."""
    if amount is None:
        return "—"
    sign = "-" if amount < 0 else ""
    digits = str(abs(int(amount)))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return f"{sign}₹{digits}"


def sharing_label(sharing: int | None) -> str:
    if sharing is None:
        return "—"
    return SHARING_LABELS.get(sharing, f"{sharing}-sharing")


def status_label(status: str | None) -> str:
    if status is None:
        return "—"
    return STATUS_LABELS.get(getattr(status, "value", status), str(status))


def fdate(d: date | None) -> str:
    return d.strftime("%d %b %Y") if d else "—"


def phone(value: str | None) -> str:
    return display_phone(value) if value else "—"
