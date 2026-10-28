from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import storage
from app.api.deps import get_tenant_or_404, require_staff
from app.core.config import settings
from app.core.db import get_db
from app.core.timeutil import parse_month
from app.models import TenantDocument, User
from app.models.enums import DocumentKind
from app.schemas import (
    DocumentOut,
    NoticeIn,
    RentRecordCreate,
    RentRecordOut,
    SettlementIn,
    SettlementOut,
    SettlementPreview,
    TenantCreate,
    TenantDetail,
    TenantSummary,
    TenantUpdate,
)
from app.services import tenants as svc
from app.services.audit import record_change
from app.services.fmt import inr
from app.services.rent import ensure_record, get_record

router = APIRouter(prefix="/api/tenants", tags=["tenants"], dependencies=[Depends(require_staff)])

DOC_LABELS = {"id_proof": "ID proof", "photo": "photo", "other": "document"}


@router.get("", response_model=list[TenantSummary])
def list_tenants(
    status: str | None = Query(None, pattern="^(current|active|on_notice|vacated)$"),
    q: str | None = None,
    db: Session = Depends(get_db),
):
    return [svc.to_summary(db, t) for t in svc.list_tenants(db, status, q)]


@router.post("", response_model=TenantDetail, status_code=201)
def create_tenant(
    data: TenantCreate, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    tenant = svc.create_tenant(db, data, user)
    db.commit()
    return svc.to_detail(db, tenant)


@router.get("/{tenant_id}", response_model=TenantDetail)
def get_tenant(tenant_id: int, db: Session = Depends(get_db)):
    return svc.to_detail(db, get_tenant_or_404(tenant_id, db))


@router.patch("/{tenant_id}", response_model=TenantDetail)
def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    tenant = svc.update_tenant(db, get_tenant_or_404(tenant_id, db), data, user)
    db.commit()
    return svc.to_detail(db, tenant)


@router.delete("/{tenant_id}", status_code=204)
def delete_tenant(
    tenant_id: int,
    confirm_name: str = Query(..., description="Must match the tenant's name exactly"),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    tenant = get_tenant_or_404(tenant_id, db)
    if confirm_name.strip() != tenant.name:
        raise HTTPException(400, "Name doesn't match. Type the tenant's name exactly to confirm.")
    svc.delete_tenant(db, tenant, user)
    db.commit()


@router.post("/{tenant_id}/notice", response_model=TenantDetail)
def give_notice(
    tenant_id: int,
    data: NoticeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    tenant = get_tenant_or_404(tenant_id, db)
    svc.give_notice(db, tenant, data.notice_date, data.move_out_date, user)
    db.commit()
    return svc.to_detail(db, tenant)


@router.get("/{tenant_id}/settlement/preview", response_model=SettlementPreview)
def settlement_preview(tenant_id: int, db: Session = Depends(get_db)):
    return svc.settlement_preview(db, get_tenant_or_404(tenant_id, db))


@router.post("/{tenant_id}/settlement", response_model=SettlementOut)
def settle(
    tenant_id: int,
    data: SettlementIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    settlement = svc.settle(db, get_tenant_or_404(tenant_id, db), data, user)
    db.commit()
    return settlement


@router.post("/{tenant_id}/rent-records", response_model=RentRecordOut, status_code=201)
def add_rent_record(
    tenant_id: int,
    data: RentRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    """Manually add a month's rent (e.g. older months for existing tenants)."""
    tenant = get_tenant_or_404(tenant_id, db)
    month = parse_month(data.month)
    if get_record(db, tenant.id, month):
        raise HTTPException(400, "A rent record for this month already exists. Edit it instead.")
    record = ensure_record(db, tenant, month, data.amount_due)
    if record is None:
        raise HTTPException(400, "That month is before the tenant's joining date.")
    record.note = data.note
    record_change(
        db, user, "rent", record.id, "create",
        f"🧾 *Rent added*: {tenant.name} (Room {tenant.room.number}) — "
        f"{month.strftime('%b %Y')} {inr(data.amount_due)}",
    )
    db.commit()
    return record


# ---------- documents ----------


@router.post("/{tenant_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    tenant_id: int,
    kind: DocumentKind = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    tenant = get_tenant_or_404(tenant_id, db)
    allowed = storage.IMAGE_TYPES if kind == DocumentKind.photo else storage.DOC_TYPES
    key, mime, size = await storage.save_upload(
        file, f"private/tenants/{tenant.id}", allowed, settings.max_upload_mb
    )
    doc = TenantDocument(
        tenant_id=tenant.id,
        kind=kind,
        storage_key=key,
        original_name=(file.filename or "file")[:255],
        mime_type=mime,
        size_bytes=size,
    )
    db.add(doc)
    record_change(
        db, user, "tenant", tenant.id, "document",
        f"📎 *{DOC_LABELS[kind.value].capitalize()} uploaded* for {tenant.name} (Room {tenant.room.number})",
    )
    db.commit()
    return doc


def _get_doc(db: Session, tenant_id: int, doc_id: int) -> TenantDocument:
    doc = db.get(TenantDocument, doc_id)
    if not doc or doc.tenant_id != tenant_id:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/{tenant_id}/documents/{doc_id}")
def download_document(tenant_id: int, doc_id: int, db: Session = Depends(get_db)):
    """Streams a private file. Only reachable with a valid staff session."""
    doc = _get_doc(db, tenant_id, doc_id)
    path = storage.path_for(doc.storage_key)
    if not path.exists():
        raise HTTPException(404, "File missing from storage")
    return FileResponse(
        path,
        media_type=doc.mime_type,
        filename=doc.original_name,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


@router.delete("/{tenant_id}/documents/{doc_id}", status_code=204)
def delete_document(
    tenant_id: int, doc_id: int, db: Session = Depends(get_db), user: User = Depends(require_staff)
):
    doc = _get_doc(db, tenant_id, doc_id)
    key = doc.storage_key
    tenant = doc.tenant
    db.delete(doc)
    record_change(
        db, user, "tenant", tenant.id, "document",
        f"🗑️ *{DOC_LABELS[doc.kind.value].capitalize()} deleted* for {tenant.name} ({doc.original_name})",
    )
    db.commit()
    storage.delete(key)
