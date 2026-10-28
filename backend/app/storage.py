"""Local-disk file storage.

Layout under STORAGE_DIR:
    private/tenants/<tenant_id>/<random>.<ext>   ID proofs, photos (served only to staff)
    public/gallery/<random>.<ext>                website gallery (served to everyone)

Files are saved under random names, and the type is detected from the file's
first bytes (not its name or the browser's claim). To move to S3 later, replace
this module with one exposing the same functions.
"""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings

ROOT = Path(settings.storage_dir).resolve()

IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
DOC_TYPES = {**IMAGE_TYPES, "application/pdf": "pdf"}
VIDEO_TYPES = {"video/mp4": "mp4", "video/webm": "webm"}

CHUNK = 1024 * 1024


def sniff(head: bytes) -> str | None:
    """Detect a file type from its magic bytes."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head[4:8] == b"ftyp":
        return "video/mp4"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    return None


def path_for(key: str) -> Path:
    """Absolute path for a storage key, refusing anything outside ROOT."""
    path = (ROOT / key).resolve()
    if not path.is_relative_to(ROOT):
        raise HTTPException(400, "Invalid file path")
    return path


async def save_upload(
    upload: UploadFile, folder: str, allowed: dict[str, str], max_mb: int
) -> tuple[str, str, int]:
    """Stream an upload to disk. Returns (storage_key, mime_type, size_bytes)."""
    head = await upload.read(16)
    mime = sniff(head)
    if mime not in allowed:
        kinds = ", ".join(sorted({v.upper() for v in allowed.values()}))
        raise HTTPException(400, f"Unsupported file type. Allowed: {kinds}")

    key = f"{folder}/{uuid.uuid4().hex}.{allowed[mime]}"
    path = path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    limit = max_mb * 1024 * 1024
    size = len(head)
    try:
        with path.open("wb") as f:
            f.write(head)
            while chunk := await upload.read(CHUNK):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File too large (max {max_mb} MB)")
                f.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return key, mime, size


def delete(key: str | None) -> None:
    if key:
        path_for(key).unlink(missing_ok=True)
