"""Website content + gallery (staff edit) and the public, no-login endpoints."""

import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import storage
from app.api.deps import require_staff
from app.core.config import settings
from app.core.db import get_db
from app.models import GalleryItem, RoomCategory, User
from app.models.enums import GalleryKind
from app.schemas import AppSettingsIO, GalleryLinkIn, GalleryOut, GalleryUpdate, SiteContent
from app.services.app_settings import (
    get_app_setting,
    get_site_content,
    set_app_setting,
    set_site_content,
)
from app.services.audit import record_change

staff = APIRouter(prefix="/api", tags=["site"], dependencies=[Depends(require_staff)])
public = APIRouter(prefix="/api/public", tags=["public"])


def _gallery_out(item: GalleryItem) -> GalleryOut:
    out = GalleryOut.model_validate(item)
    if item.storage_key:
        out.media_url = f"/api/public/media/{item.storage_key.removeprefix('public/')}"
    return out


# ---------- private app settings ----------


@staff.get("/settings", response_model=AppSettingsIO)
def get_settings(db: Session = Depends(get_db)):
    return AppSettingsIO(
        owner_whatsapp=get_app_setting(db, "owner_whatsapp") or "",
        payment_note=get_app_setting(db, "payment_note") or "",
    )


@staff.put("/settings", response_model=AppSettingsIO)
def put_settings(
    data: AppSettingsIO, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    old_owner = get_app_setting(db, "owner_whatsapp")
    set_app_setting(db, "owner_whatsapp", data.owner_whatsapp)
    set_app_setting(db, "payment_note", data.payment_note)
    record_change(
        db, user, "settings", None, "update",
        "⚙️ *Settings updated*"
        + (f"\n• Owner WhatsApp changed to {data.owner_whatsapp}" if old_owner != data.owner_whatsapp else ""),
    )
    db.commit()
    return data


# ---------- site content ----------


@staff.get("/site", response_model=SiteContent)
def get_site(db: Session = Depends(get_db)):
    return get_site_content(db)


@staff.put("/site", response_model=SiteContent)
def put_site(data: SiteContent, db: Session = Depends(get_db), user: User = Depends(require_staff)):
    values = data.model_dump()
    values["amenities"] = [a.strip() for a in data.amenities if a.strip()]
    values["rules"] = [r.strip() for r in data.rules if r.strip()]
    set_site_content(db, values)
    record_change(db, user, "site", None, "update", "🌐 Website content updated", notify=False)
    db.commit()
    return values


# ---------- gallery ----------


@staff.get("/gallery", response_model=list[GalleryOut])
def list_gallery(db: Session = Depends(get_db)):
    items = db.scalars(select(GalleryItem).order_by(GalleryItem.sort_order, GalleryItem.id)).all()
    return [_gallery_out(i) for i in items]


def _next_order(db: Session) -> int:
    return (db.scalar(select(func.max(GalleryItem.sort_order))) or 0) + 1


@staff.post("/gallery/upload", response_model=GalleryOut, status_code=201)
async def upload_gallery(
    file: UploadFile = File(...),
    caption: str = Form(""),
    db: Session = Depends(get_db),
):
    head = await file.read(16)
    await file.seek(0)
    is_video = (storage.sniff(head) or "").startswith("video/")
    key, mime, _ = await storage.save_upload(
        file,
        "public/gallery",
        storage.VIDEO_TYPES if is_video else storage.IMAGE_TYPES,
        settings.max_video_mb if is_video else settings.max_upload_mb,
    )
    item = GalleryItem(
        kind=GalleryKind.video if is_video else GalleryKind.photo,
        storage_key=key,
        mime_type=mime,
        caption=caption[:200],
        sort_order=_next_order(db),
    )
    db.add(item)
    db.commit()
    return _gallery_out(item)


_YOUTUBE = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([\w-]{11})")


@staff.post("/gallery/link", response_model=GalleryOut, status_code=201)
def add_gallery_link(data: GalleryLinkIn, db: Session = Depends(get_db)):
    """Add a YouTube video by link (stored as an embeddable URL)."""
    match = _YOUTUBE.search(data.url)
    if not match:
        raise HTTPException(400, "Paste a YouTube link (youtube.com/watch?v=… or youtu.be/…)")
    item = GalleryItem(
        kind=GalleryKind.video_url,
        url=f"https://www.youtube-nocookie.com/embed/{match.group(1)}",
        caption=data.caption,
        sort_order=_next_order(db),
    )
    db.add(item)
    db.commit()
    return _gallery_out(item)


@staff.patch("/gallery/{item_id}", response_model=GalleryOut)
def update_gallery(item_id: int, data: GalleryUpdate, db: Session = Depends(get_db)):
    item = db.get(GalleryItem, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    if data.caption is not None:
        item.caption = data.caption
    if data.sort_order is not None:
        item.sort_order = data.sort_order
    db.commit()
    return _gallery_out(item)


@staff.delete("/gallery/{item_id}", status_code=204)
def delete_gallery(item_id: int, db: Session = Depends(get_db)):
    item = db.get(GalleryItem, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    key = item.storage_key
    db.delete(item)
    db.commit()
    storage.delete(key)


# ---------- public (no login) ----------


@public.get("/site")
def public_site(db: Session = Depends(get_db)):
    content = get_site_content(db)
    categories = db.scalars(
        select(RoomCategory).options(selectinload(RoomCategory.rates)).order_by(RoomCategory.sort_order)
    ).all()
    prices = []
    if content.get("show_prices", True):
        for c in categories:
            rates = [
                {"sharing": r.sharing, "monthly_rent": r.monthly_rent}
                for r in c.rates
                if r.monthly_rent is not None
            ]
            prices.append(
                {"name": c.name, "description": c.description, "max_sharing": c.max_sharing, "rates": rates}
            )
    items = db.scalars(select(GalleryItem).order_by(GalleryItem.sort_order, GalleryItem.id)).all()
    return {
        "content": content,
        "prices": prices,
        "gallery": [_gallery_out(i).model_dump() for i in items],
    }


@public.get("/media/{path:path}")
def public_media(path: str):
    """Serve public gallery files only (never anything under private/)."""
    file_path = storage.path_for(f"public/{path}")
    if not file_path.is_relative_to(storage.ROOT / "public") or not file_path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(file_path, headers={"Cache-Control": "public, max-age=86400"})
