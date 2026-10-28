"""WhatsApp message texts. *bold* and _italic_ are WhatsApp formatting."""

from datetime import date

from app.core.timeutil import month_label
from app.models import Tenant
from app.services.fmt import fdate, inr, phone
from app.services.rent import Due


def rent_reminder(
    pg: str, tenant: Tenant, dues: list[Due], deposit_balance: int, payment_note: str
) -> str:
    first_name = tenant.name.split()[0] if tenant.name.strip() else tenant.name
    lines = [f"Hi {first_name}, this is a gentle reminder from *{pg}*.", ""]
    if dues:
        lines.append("Rent pending:")
        lines += [f"• {month_label(d.month)}: {inr(d.balance)}" for d in dues]
    if deposit_balance > 0:
        lines.append(f"• Security deposit balance: {inr(deposit_balance)}")
    total = sum(d.balance for d in dues) + deposit_balance
    lines += ["", f"*Total due: {inr(total)}*", ""]
    if payment_note:
        lines += [payment_note.strip(), ""]
    lines.append("Please pay at the earliest. Kindly ignore if already paid. Thank you!")
    return "\n".join(lines)


def owner_report(month: date, as_of: date, rows: list[dict]) -> str:
    if not rows:
        return f"✅ *Rent report — {month_label(month)}*\nEveryone has paid in full as of {fdate(as_of)}. 🎉"
    lines = [f"📋 *Unpaid rent — {month_label(month)}* (as of {fdate(as_of)})", ""]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. {row['name']} — Room {row['room']} — {phone(row['phone'])} — "
            f"{inr(row['amount'])} ({row['label']})"
        )
    total = sum(r["amount"] for r in rows)
    lines += ["", f"*Total pending: {inr(total)}* from {len(rows)} tenant(s)"]
    return "\n".join(lines)
