from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.attachment import Attachment
from app.services.attachment_service import (
    AttachmentError,
    list_attachments,
    read_storage_bytes,
    sniff_content_type,
    soft_delete_attachment,
    upload_attachment,
)


@pytest.fixture(autouse=True)
def isolate_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("ATTACHMENT_STORAGE_ROOT", str(tmp_path))
    yield


PDF_BYTES = b"%PDF-1.4\n%fake"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_sniff_pdf():
    assert sniff_content_type(PDF_BYTES, "x.pdf") == "application/pdf"


def test_sniff_png():
    assert sniff_content_type(PNG_BYTES, "x.png") == "image/png"


def test_sniff_text_plain_by_extension():
    assert sniff_content_type(b"hello world", "notes.txt") == "text/plain"


def test_sniff_csv_by_extension():
    assert sniff_content_type(b"a,b,c\n1,2,3", "data.csv") == "text/csv"


def test_sniff_unknown_rejected():
    with pytest.raises(AttachmentError):
        sniff_content_type(b"\x00\x01\x02\x03", "mystery.bin")


@pytest.mark.asyncio
async def test_upload_and_list_pdf(db_session):
    rid = uuid.uuid4()
    att = await upload_attachment(
        db_session,
        scope="bill",
        record_id=rid,
        filename="receipt.pdf",
        data=PDF_BYTES,
    )
    await db_session.commit()
    assert att.content_type == "application/pdf"
    assert att.size_bytes == len(PDF_BYTES)
    assert att.thumbnail_storage_key is None  # PDF has no thumbnail

    rows = await list_attachments(db_session, scope="bill", record_id=rid)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_upload_unsupported_scope_rejected(db_session):
    with pytest.raises(AttachmentError):
        await upload_attachment(
            db_session,
            scope="not_a_real_scope",
            record_id=uuid.uuid4(),
            filename="x.pdf",
            data=PDF_BYTES,
        )


@pytest.mark.asyncio
async def test_upload_empty_rejected(db_session):
    with pytest.raises(AttachmentError):
        await upload_attachment(
            db_session,
            scope="bill",
            record_id=uuid.uuid4(),
            filename="x.pdf",
            data=b"",
        )


@pytest.mark.asyncio
async def test_upload_oversize_rejected(db_session, monkeypatch):
    # Patch the cap to a tiny value so we don't generate 20 MB
    monkeypatch.setattr("app.services.attachment_service.MAX_FILE_BYTES", 16)
    with pytest.raises(AttachmentError):
        await upload_attachment(
            db_session,
            scope="bill",
            record_id=uuid.uuid4(),
            filename="x.pdf",
            data=PDF_BYTES + b"x" * 100,
        )


@pytest.mark.asyncio
async def test_upload_disallowed_type_rejected(db_session):
    with pytest.raises(AttachmentError):
        await upload_attachment(
            db_session,
            scope="bill",
            record_id=uuid.uuid4(),
            filename="evil.exe",
            data=b"MZ\x90\x00",
        )


@pytest.mark.asyncio
async def test_soft_delete_hides_from_list(db_session):
    rid = uuid.uuid4()
    att = await upload_attachment(
        db_session,
        scope="invoice",
        record_id=rid,
        filename="r.pdf",
        data=PDF_BYTES,
    )
    await db_session.commit()
    rows = await list_attachments(db_session, scope="invoice", record_id=rid)
    assert len(rows) == 1

    await soft_delete_attachment(db_session, attachment_id=att.id)
    await db_session.commit()
    rows = await list_attachments(db_session, scope="invoice", record_id=rid)
    assert rows == []
    # Underlying row still present, just deleted_at set
    raw = (await db_session.execute(select(Attachment).where(Attachment.id == att.id))).scalar_one()
    assert raw.deleted_at is not None


@pytest.mark.asyncio
async def test_path_traversal_via_filename_blocked(db_session):
    # Filenames with ../ components get sanitized in `_sanitize_filename`
    # to a flat name, so path traversal is impossible. Verify the
    # sanitizer catches the obvious cases.
    rid = uuid.uuid4()
    att = await upload_attachment(
        db_session,
        scope="bill",
        record_id=rid,
        filename="../../etc/passwd.txt",
        data=b"plaintext content",
    )
    await db_session.commit()
    # Sanitized filename should not contain path separators
    assert "/" not in att.filename
    # And the file lives inside the configured storage root
    root = Path(os.environ["ATTACHMENT_STORAGE_ROOT"]).resolve()
    full = (root / att.storage_key).resolve()
    assert str(full).startswith(str(root))


@pytest.mark.asyncio
async def test_image_thumbnail_generated(db_session):
    rid = uuid.uuid4()
    # Build a minimal valid PNG via Pillow so the magic bytes match and
    # Pillow can actually generate a thumbnail.
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color="red").save(buf, format="PNG")
    png = buf.getvalue()

    att = await upload_attachment(
        db_session,
        scope="job",
        record_id=rid,
        filename="ref.png",
        data=png,
    )
    await db_session.commit()
    assert att.thumbnail_storage_key is not None
    thumb_bytes = read_storage_bytes(att.thumbnail_storage_key)
    assert thumb_bytes  # non-empty


@pytest.mark.asyncio
async def test_per_record_size_cap(db_session, monkeypatch):
    # Lower the per-record cap to two PDFs worth + some
    monkeypatch.setattr("app.services.attachment_service.MAX_RECORD_BYTES", len(PDF_BYTES) * 2 + 1)
    rid = uuid.uuid4()
    await upload_attachment(db_session, scope="bill", record_id=rid, filename="a.pdf", data=PDF_BYTES)
    await upload_attachment(db_session, scope="bill", record_id=rid, filename="b.pdf", data=PDF_BYTES)
    with pytest.raises(AttachmentError):
        await upload_attachment(db_session, scope="bill", record_id=rid, filename="c.pdf", data=PDF_BYTES)
