"""Attachment storage and lifecycle (#250 Phase 1).

Local-filesystem storage behind a Protocol so swapping to S3 later is
isolated. Path-traversal protected, MIME-sniffed (magic-byte check on a
small allowlist; no python-magic dep), Pillow thumbnails for images.

Phase 1 deliberately keeps this self-contained:
- No virus scanning.
- No HEIC support (would require pillow-heif).
- No editable size limits (constants below; revisit per-resource later).
- No S3.
- No email attach hook (#244 Phase 2 will wire this in).
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment


class AttachmentError(RuntimeError):
    pass


VALID_SCOPES: Final[set[str]] = {
    "bill",
    "invoice",
    "quote",
    "credit_note",
    "debit_note",
    "sale",
    "job",
    "product",
    "customer",
    "vendor",
    "material",
    "supply",
    "fixed_asset",
    "bank_reconciliation",
    "expense_claim",
}

MAX_FILE_BYTES: Final[int] = 20 * 1024 * 1024  # 20 MB
MAX_RECORD_BYTES: Final[int] = 100 * 1024 * 1024  # 100 MB

# Magic-byte signatures for the allowed types. Each entry is a list of
# (offset, byte_pattern) pairs that must all match. The accompanying
# content_type string is what we persist on the row.
_MAGIC_TABLE: Final[list[tuple[str, list[tuple[int, bytes]]]]] = [
    ("application/pdf", [(0, b"%PDF-")]),
    ("image/png", [(0, b"\x89PNG\r\n\x1a\n")]),
    ("image/jpeg", [(0, b"\xff\xd8\xff")]),
    ("image/gif", [(0, b"GIF87a")]),
    ("image/gif", [(0, b"GIF89a")]),
    ("image/webp", [(0, b"RIFF"), (8, b"WEBP")]),
    # STL ASCII files start with "solid ". Binary STLs have no magic, so
    # we skip them in v1; binary STLs masquerade-test would need geometry.
    ("model/stl", [(0, b"solid ")]),
    # 3MF is a ZIP container.
    ("model/3mf", [(0, b"PK\x03\x04")]),
    ("text/plain", []),  # fallback
    ("text/csv", []),    # fallback
]

_IMAGE_TYPES: Final[set[str]] = {"image/png", "image/jpeg", "image/gif", "image/webp"}

EXTENSION_MAP: Final[dict[str, str]] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "model/stl": "stl",
    "model/3mf": "3mf",
    "text/plain": "txt",
    "text/csv": "csv",
}


def _storage_root() -> Path:
    return Path(os.environ.get("ATTACHMENT_STORAGE_ROOT", "/var/app-attachments"))


def sniff_content_type(data: bytes, filename: str | None) -> str:
    """Return one of the allowlisted content-types or raise AttachmentError.

    Sniffs the magic table first; falls back to extension for plaintext
    types (text/plain, text/csv) which have no header signature.
    """
    for ct, patterns in _MAGIC_TABLE:
        if not patterns:
            continue
        if all(data[off : off + len(p)] == p for off, p in patterns):
            return ct
    # Fallback by extension for text-y files
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ("txt",):
            return "text/plain"
        if ext in ("csv", "tsv"):
            return "text/csv"
    raise AttachmentError("File type not allowed or unrecognised")


def _sanitize_filename(name: str) -> str:
    # Strip path components and keep a conservative character set.
    base = os.path.basename(name)
    safe = "".join(c for c in base if c.isalnum() or c in (" ", ".", "_", "-")).strip()
    return safe[:200] or "untitled"


def _build_storage_key(scope: str, ext: str) -> str:
    now = datetime.now(timezone.utc)
    return f"{scope}/{now.year:04d}/{now.month:02d}/{uuid.uuid4().hex}.{ext}"


def _resolve_path(storage_key: str) -> Path:
    root = _storage_root().resolve()
    p = (root / storage_key).resolve()
    # Path-traversal protection: result must stay inside root
    if not str(p).startswith(str(root) + os.sep) and p != root:
        raise AttachmentError("Path traversal blocked")
    return p


def _generate_thumbnail(data: bytes, content_type: str) -> bytes | None:
    if content_type not in _IMAGE_TYPES:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((256, 256))
        buf = io.BytesIO()
        # Convert to webp for compactness; respect alpha when present.
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.save(buf, format="WEBP", quality=80)
        return buf.getvalue()
    except Exception:
        return None


async def upload_attachment(
    db: AsyncSession,
    *,
    scope: str,
    record_id: uuid.UUID,
    filename: str,
    data: bytes,
    description: str | None = None,
    uploaded_by_user_id: uuid.UUID | None = None,
) -> Attachment:
    if scope not in VALID_SCOPES:
        raise AttachmentError(f"Unsupported attachment scope: {scope!r}")
    if not data:
        raise AttachmentError("Empty file")
    if len(data) > MAX_FILE_BYTES:
        raise AttachmentError(f"File exceeds {MAX_FILE_BYTES // 1024 // 1024} MB limit")

    # Per-record size cap
    existing_total = sum(
        (
            r.size_bytes
            for r in (
                await db.execute(
                    select(Attachment).where(
                        Attachment.scope == scope,
                        Attachment.record_id == record_id,
                        Attachment.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
        ),
        0,
    )
    if existing_total + len(data) > MAX_RECORD_BYTES:
        raise AttachmentError(
            f"Per-record total {MAX_RECORD_BYTES // 1024 // 1024} MB cap would be exceeded"
        )

    safe_name = _sanitize_filename(filename)
    content_type = sniff_content_type(data, safe_name)
    ext = EXTENSION_MAP.get(content_type, "bin")

    storage_key = _build_storage_key(scope, ext)
    target = _resolve_path(storage_key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    thumbnail_key = None
    thumb = _generate_thumbnail(data, content_type)
    if thumb is not None:
        thumbnail_key = storage_key + ".thumb.webp"
        thumb_target = _resolve_path(thumbnail_key)
        thumb_target.write_bytes(thumb)

    sha = hashlib.sha256(data).hexdigest()

    att = Attachment(
        scope=scope,
        record_id=record_id,
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        storage_key=storage_key,
        thumbnail_storage_key=thumbnail_key,
        sha256=sha,
        description=description,
        uploaded_by_user_id=uploaded_by_user_id,
    )
    db.add(att)
    await db.flush()
    return att


async def list_attachments(
    db: AsyncSession,
    *,
    scope: str,
    record_id: uuid.UUID,
) -> list[Attachment]:
    if scope not in VALID_SCOPES:
        raise AttachmentError(f"Unsupported attachment scope: {scope!r}")
    return list(
        (
            await db.execute(
                select(Attachment)
                .where(
                    Attachment.scope == scope,
                    Attachment.record_id == record_id,
                    Attachment.deleted_at.is_(None),
                )
                .order_by(Attachment.uploaded_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def soft_delete_attachment(
    db: AsyncSession,
    *,
    attachment_id: uuid.UUID,
    deleted_by_user_id: uuid.UUID | None = None,
) -> None:
    att = (await db.execute(select(Attachment).where(Attachment.id == attachment_id))).scalar_one_or_none()
    if att is None:
        raise AttachmentError("Attachment not found")
    if att.deleted_at is not None:
        return
    att.deleted_at = datetime.now(timezone.utc)
    att.deleted_by_user_id = deleted_by_user_id
    await db.flush()


def read_storage_bytes(storage_key: str) -> bytes:
    """Return the on-disk bytes for a storage_key. Endpoint streams these
    back to the client."""
    p = _resolve_path(storage_key)
    if not p.exists():
        raise AttachmentError("Underlying file is missing")
    return p.read_bytes()
