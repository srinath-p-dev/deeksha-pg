"""Key/value settings stored in the database (editable from the dashboard)."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting, SiteSetting

# Private settings and their defaults
APP_DEFAULTS: dict[str, Any] = {
    "owner_whatsapp": "",  # 91XXXXXXXXXX; receives change alerts + monthly report
    "payment_note": "",  # appended to rent reminders, e.g. "UPI: yourpg@okaxis"
}

# Public website content and defaults
SITE_DEFAULTS: dict[str, Any] = {
    "pg_name": "My PG",
    "tagline": "",
    "about": "",
    "who_can_stay": "",
    "address": "",
    "maps_link": "",
    "phone": "",
    "whatsapp": "",
    "food": "",
    "amenities": [],
    "rules": [],
    "show_prices": True,
}


def get_app_setting(db: Session, key: str) -> Any:
    row = db.get(AppSetting, key)
    return row.value if row else APP_DEFAULTS.get(key)


def set_app_setting(db: Session, key: str, value: Any) -> None:
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))


def get_site_content(db: Session) -> dict[str, Any]:
    content = dict(SITE_DEFAULTS)
    for row in db.query(SiteSetting).all():
        if row.key in SITE_DEFAULTS:
            content[row.key] = row.value
    return content


def set_site_content(db: Session, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if key not in SITE_DEFAULTS:
            continue
        row = db.get(SiteSetting, key)
        if row:
            row.value = value
        else:
            db.add(SiteSetting(key=key, value=value))


def pg_name(db: Session) -> str:
    return get_site_content(db)["pg_name"] or "PG"
