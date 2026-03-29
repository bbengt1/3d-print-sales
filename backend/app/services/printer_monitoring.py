from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.printer import Printer

DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_STALE_AFTER_MINUTES = 10
SUPPORTED_PROVIDERS = {"octoprint"}


@dataclass
class ProviderTestResult:
    ok: bool
    provider: str
    normalized_status: str | None = None
    online: bool | None = None
    message: str | None = None
    raw: dict[str, Any] | None = None


class PrinterMonitoringError(Exception):
    pass


class UnsupportedPrinterProviderError(PrinterMonitoringError):
    pass


class PrinterMonitorProvider:
    provider_name: str

    async def test_connection(self, printer: Printer) -> ProviderTestResult:
        raise NotImplementedError

    async def fetch_live_state(self, printer: Printer) -> dict[str, Any]:
        raise NotImplementedError


class OctoPrintMonitorProvider(PrinterMonitorProvider):
    provider_name = "octoprint"

    async def _request(self, printer: Printer, path: str) -> dict[str, Any]:
        if not printer.monitor_base_url:
            raise PrinterMonitoringError("Monitoring base URL is required for OctoPrint")

        headers: dict[str, str] = {}
        if printer.monitor_api_key:
            headers["X-Api-Key"] = printer.monitor_api_key

        timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
        url = f"{printer.monitor_base_url.rstrip('/')}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    def _normalize_status(self, state_text: str | None, flags: dict[str, Any] | None) -> tuple[str, bool]:
        text = (state_text or "").strip().lower()
        flags = flags or {}

        if flags.get("error"):
            return "error", True
        if flags.get("paused") or "pause" in text:
            return "paused", True
        if flags.get("printing") or "print" in text:
            return "printing", True
        if flags.get("ready") or flags.get("operational") or text in {"operational", "ready"}:
            return "idle", True
        if flags.get("closedOrError"):
            return "offline", False
        if text in {"offline", "disconnected"}:
            return "offline", False
        return "idle", True

    async def test_connection(self, printer: Printer) -> ProviderTestResult:
        payload = await self._request(printer, "/api/printer")
        state = payload.get("state", {})
        normalized_status, online = self._normalize_status(state.get("text"), state.get("flags"))
        return ProviderTestResult(
            ok=True,
            provider=self.provider_name,
            normalized_status=normalized_status,
            online=online,
            message=state.get("text") or "Connection successful",
            raw=payload,
        )

    async def fetch_live_state(self, printer: Printer) -> dict[str, Any]:
        printer_payload, job_payload = await _gather_octoprint_payloads(self, printer)
        state = printer_payload.get("state", {})
        temp = printer_payload.get("temperature", {})
        progress = (job_payload.get("progress") or {})
        job = job_payload.get("job") or {}

        normalized_status, online = self._normalize_status(state.get("text"), state.get("flags"))
        bed_actual = _to_float((temp.get("bed") or {}).get("actual"))
        tool_actual = _extract_tool_actual(temp)
        completion = _to_float(progress.get("completion"))
        file_name = ((job.get("file") or {}).get("name")) or job.get("filename")

        now = datetime.now(timezone.utc)
        return {
            "monitor_online": online,
            "status": normalized_status,
            "monitor_status": normalized_status,
            "monitor_progress_percent": completion,
            "current_print_name": file_name,
            "monitor_last_message": state.get("text"),
            "monitor_bed_temp_c": bed_actual,
            "monitor_tool_temp_c": tool_actual,
            "monitor_last_seen_at": now,
            "monitor_last_updated_at": now,
            "monitor_last_error": None,
        }


async def _gather_octoprint_payloads(provider: OctoPrintMonitorProvider, printer: Printer) -> tuple[dict[str, Any], dict[str, Any]]:
    printer_payload = await provider._request(printer, "/api/printer")
    job_payload = await provider._request(printer, "/api/job")
    return printer_payload, job_payload


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_tool_actual(temp_payload: dict[str, Any]) -> float | None:
    for key in ("tool0", "tool1"):
        value = (temp_payload.get(key) or {}).get("actual")
        if value is not None:
            return _to_float(value)
    return None


def get_provider(printer: Printer) -> PrinterMonitorProvider:
    provider = (printer.monitor_provider or "").strip().lower()
    if provider == "octoprint":
        return OctoPrintMonitorProvider()
    raise UnsupportedPrinterProviderError(f"Unsupported monitor provider '{printer.monitor_provider}'")


async def test_printer_connection(printer: Printer) -> ProviderTestResult:
    if not printer.monitor_provider:
        return ProviderTestResult(ok=False, provider="unconfigured", message="Monitoring provider is not configured")
    provider = get_provider(printer)
    return await provider.test_connection(printer)


async def refresh_printer_monitoring(db: AsyncSession, printer: Printer, *, force: bool = False) -> Printer:
    if not printer.monitor_enabled or not printer.monitor_provider or not printer.monitor_base_url:
        return printer

    if not force and not _should_refresh(printer):
        return printer

    try:
        provider = get_provider(printer)
        updates = await provider.fetch_live_state(printer)
        for field, value in updates.items():
            setattr(printer, field, value)
    except Exception as exc:  # noqa: BLE001
        now = datetime.now(timezone.utc)
        printer.monitor_online = False
        printer.monitor_status = "offline"
        printer.status = "offline"
        printer.monitor_last_error = str(exc)
        printer.monitor_last_message = str(exc)
        printer.monitor_last_updated_at = now
    await db.commit()
    await db.refresh(printer)
    return printer


def _should_refresh(printer: Printer) -> bool:
    interval = max(5, printer.monitor_poll_interval_seconds or 30)
    if printer.monitor_last_updated_at is None:
        return True
    return datetime.now(timezone.utc) - printer.monitor_last_updated_at >= timedelta(seconds=interval)


def mark_printer_stale_if_needed(printer: Printer) -> Printer:
    if not printer.monitor_enabled:
        return printer
    if printer.monitor_last_seen_at is None:
        return printer
    stale_after = timedelta(minutes=DEFAULT_STALE_AFTER_MINUTES)
    if datetime.now(timezone.utc) - printer.monitor_last_seen_at > stale_after:
        printer.monitor_online = False
        printer.monitor_status = "offline"
        printer.status = "offline"
    return printer
