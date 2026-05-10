"""#276 P1 (Codex review): the attachments upload endpoint must reject
oversized payloads BEFORE buffering the entire request body in memory.

Previously the endpoint did `data = await file.read()` and only then
deferred to `upload_attachment`'s MAX_FILE_BYTES check, meaning an
authenticated client could force the worker to allocate arbitrarily
large bytes objects up to whatever the proxy/body-size limit allowed.

The fix streams `UploadFile.read(chunk_size)` and aborts with HTTP 413
as soon as the cumulative size exceeds MAX_FILE_BYTES, so we never
buffer more than ~MAX_FILE_BYTES + one chunk. We verify that here both
by confirming the 413 status and by spying on the read calls to make
sure the endpoint stops reading once the cap is breached.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.api.v1.endpoints import attachments as attachments_endpoint
from app.services import attachment_service


@pytest_asyncio.fixture(autouse=True)
async def isolate_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("ATTACHMENT_STORAGE_ROOT", str(tmp_path))
    yield


@pytest.mark.asyncio
async def test_oversize_upload_rejected_with_413(
    client: AsyncClient, auth_headers, monkeypatch
):
    # Shrink the cap so we can exercise the streaming guard without
    # allocating 20 MB. Keep the chunk size small enough that the
    # streaming loop iterates more than once.
    monkeypatch.setattr(attachment_service, "MAX_FILE_BYTES", 1024)
    monkeypatch.setattr(attachments_endpoint, "MAX_FILE_BYTES", 1024)
    monkeypatch.setattr(attachments_endpoint, "_UPLOAD_CHUNK_SIZE", 256)

    payload = b"%PDF-1.4\n" + b"x" * (4 * 1024)  # 4x over the cap
    r = await client.post(
        f"/api/v1/attachments/bill/{uuid.uuid4()}",
        files={"file": ("big.pdf", payload, "application/pdf")},
        headers=auth_headers,
    )
    assert r.status_code == 413, r.text
    assert "limit" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_oversize_upload_does_not_buffer_full_body(
    client: AsyncClient, auth_headers, monkeypatch
):
    """The streaming guard must short-circuit before reading the entire
    body. We monkeypatch the endpoint's chunk reader to count bytes
    drained and assert that we never read materially more than the cap."""

    monkeypatch.setattr(attachment_service, "MAX_FILE_BYTES", 1024)
    monkeypatch.setattr(attachments_endpoint, "MAX_FILE_BYTES", 1024)
    monkeypatch.setattr(attachments_endpoint, "_UPLOAD_CHUNK_SIZE", 256)

    # Wrap UploadFile.read to track how many bytes the endpoint pulls
    # before bailing.
    from starlette.datastructures import UploadFile as StarletteUploadFile

    bytes_read: list[int] = []
    original_read = StarletteUploadFile.read

    async def tracking_read(self: Any, size: int = -1) -> bytes:
        chunk = await original_read(self, size)
        bytes_read.append(len(chunk))
        return chunk

    monkeypatch.setattr(StarletteUploadFile, "read", tracking_read)

    # 64 KB body — far larger than the 1 KB cap, so a non-streaming
    # implementation would read all 64 KB before rejecting.
    payload = b"%PDF-1.4\n" + b"x" * (64 * 1024)
    r = await client.post(
        f"/api/v1/attachments/bill/{uuid.uuid4()}",
        files={"file": ("big.pdf", payload, "application/pdf")},
        headers=auth_headers,
    )
    assert r.status_code == 413, r.text

    total_bytes_read = sum(bytes_read)
    # Tight bound: the endpoint must abort once the cap is exceeded, so
    # it should never drain more than the cap plus a single chunk's
    # worth of overshoot. Anything close to len(payload) means the body
    # is being fully buffered (the bug).
    assert total_bytes_read <= 1024 + 256, (
        f"endpoint buffered {total_bytes_read} bytes (cap=1024, chunk=256); "
        "streaming guard appears to be missing"
    )


@pytest.mark.asyncio
async def test_normal_upload_still_works(
    client: AsyncClient, auth_headers
):
    """Sanity check: the streaming changes don't break the happy path."""
    payload = b"%PDF-1.4\nhello world"
    r = await client.post(
        f"/api/v1/attachments/bill/{uuid.uuid4()}",
        files={"file": ("ok.pdf", payload, "application/pdf")},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["filename"].endswith(".pdf")
    assert body["size_bytes"] == len(payload)
