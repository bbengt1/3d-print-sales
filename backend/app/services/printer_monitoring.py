from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
import websockets
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.printer import Printer

DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_STALE_AFTER_MINUTES = 10
MOONRAKER_WS_STALE_AFTER_SECONDS = 45
MOONRAKER_WS_RECONNECT_DELAY_SECONDS = 5
SUPPORTED_PROVIDERS = {"octoprint", "moonraker"}


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


class HttpPrinterMonitorProvider(PrinterMonitorProvider):
    auth_header_name: str | None = None

    def _build_headers(self, printer: Printer) -> dict[str, str]:
        if self.auth_header_name and printer.monitor_api_key:
            return {self.auth_header_name: printer.monitor_api_key}
        return {}

    def _build_url(self, printer: Printer, path: str) -> str:
        if not printer.monitor_base_url:
            raise PrinterMonitoringError(f"Monitoring base URL is required for {self.provider_name}")
        return f"{printer.monitor_base_url.rstrip('/')}{path}"

    async def _request(self, printer: Printer, path: str) -> dict[str, Any]:
        timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS)
        url = self._build_url(printer, path)
        headers = self._build_headers(printer)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()


class OctoPrintMonitorProvider(HttpPrinterMonitorProvider):
    provider_name = "octoprint"
    auth_header_name = "X-Api-Key"

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
            "monitor_current_layer": None,
            "monitor_total_layers": None,
            "monitor_elapsed_seconds": None,
            "monitor_remaining_seconds": None,
            "monitor_eta_at": None,
            "monitor_bed_target_c": _to_float((temp.get("bed") or {}).get("target")),
            "monitor_tool_target_c": _extract_tool_target(temp),
            "monitor_last_event_type": None,
            "monitor_last_event_at": None,
            "monitor_ws_connected": None,
            "monitor_ws_last_error": None,
        }


class MoonrakerMonitorProvider(HttpPrinterMonitorProvider):
    provider_name = "moonraker"
    auth_header_name = "X-Api-Key"

    def _normalize_status(
        self,
        *,
        server_state: str | None,
        printer_state: str | None,
        print_state: str | None,
        sdcard_active: bool | None,
    ) -> tuple[str, bool]:
        server = (server_state or "").strip().lower()
        printer = (printer_state or "").strip().lower()
        job = (print_state or "").strip().lower()

        if server and server not in {"ready"}:
            if server in {"error", "shutdown"}:
                return "error", True
            if server in {"startup", "loading", "initializing"}:
                return "maintenance", True
            if server in {"disconnected", "offline"}:
                return "offline", False

        if printer in {"error", "shutdown"}:
            return "error", True
        if printer in {"startup", "initializing"}:
            return "maintenance", True
        if printer in {"disconnected", "offline"}:
            return "offline", False

        if job in {"paused"}:
            return "paused", True
        if job in {"printing"} or bool(sdcard_active):
            return "printing", True
        if job in {"error", "cancelled", "canceled", "complete", "standby"}:
            return "idle", True
        if printer in {"paused"}:
            return "paused", True
        if printer in {"printing"}:
            return "printing", True
        if printer in {"ready", "standby"}:
            return "idle", True
        return "idle", True

    async def test_connection(self, printer: Printer) -> ProviderTestResult:
        server_payload = await self._request(printer, "/server/info")
        printer_payload = await self._request(printer, "/printer/info")
        server_info = server_payload.get("result") or {}
        printer_info = printer_payload.get("result") or {}
        normalized_status, online = self._normalize_status(
            server_state=server_info.get("klippy_state"),
            printer_state=printer_info.get("state"),
            print_state=None,
            sdcard_active=None,
        )
        message = printer_info.get("state_message") or f"Moonraker {server_info.get('moonraker_version', 'connected')}"
        return ProviderTestResult(
            ok=True,
            provider=self.provider_name,
            normalized_status=normalized_status,
            online=online,
            message=message,
            raw={"server": server_payload, "printer": printer_payload},
        )

    async def fetch_live_state(self, printer: Printer) -> dict[str, Any]:
        await moonraker_websocket_manager.ensure_tracking(printer)
        snapshot = moonraker_websocket_manager.get_snapshot(printer.id)
        if snapshot and _snapshot_is_fresh(snapshot):
            return dict(snapshot)

        server_payload, printer_payload, objects_payload = await _gather_moonraker_payloads(self, printer)
        updates = _build_moonraker_state_from_poll(server_payload, printer_payload, objects_payload)
        snapshot = moonraker_websocket_manager.merge_polled_state(printer.id, updates)
        return dict(snapshot)


class MoonrakerWebsocketManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._counter = count(1)
        self._lock = asyncio.Lock()

    async def ensure_tracking(self, printer: Printer) -> None:
        if not printer.monitor_base_url:
            return

        key = str(printer.id)
        config = {
            "printer_id": key,
            "base_url": printer.monitor_base_url,
            "api_key": printer.monitor_api_key,
        }
        async with self._lock:
            previous = self._configs.get(key)
            task = self._tasks.get(key)
            needs_restart = previous != config and task is not None
            if needs_restart:
                task.cancel()
                self._tasks.pop(key, None)
            self._configs[key] = config
            task = self._tasks.get(key)
            if task is None or task.done():
                self._tasks[key] = asyncio.create_task(self._run_connection(key), name=f"moonraker-ws-{key}")

    def get_snapshot(self, printer_id: Any) -> dict[str, Any] | None:
        snapshot = self._snapshots.get(str(printer_id))
        return dict(snapshot) if snapshot else None

    def merge_polled_state(self, printer_id: Any, updates: dict[str, Any]) -> dict[str, Any]:
        key = str(printer_id)
        snapshot = dict(self._snapshots.get(key) or {})
        snapshot.update(updates)
        snapshot.setdefault("monitor_ws_connected", False)
        snapshot.setdefault("monitor_ws_last_error", None)
        self._snapshots[key] = snapshot
        return snapshot

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_connection(self, printer_id: str) -> None:
        while True:
            config = self._configs.get(printer_id)
            if not config:
                return

            request_id = next(self._counter)
            ws_url = _build_moonraker_websocket_url(config["base_url"], config.get("api_key"))
            try:
                async with websockets.connect(ws_url, open_timeout=DEFAULT_TIMEOUT_SECONDS) as websocket:
                    await self._set_connection_state(printer_id, connected=True, error=None)
                    await websocket.send(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "method": "printer.objects.subscribe",
                                "id": request_id,
                                "params": {
                                    "objects": {
                                        "print_stats": None,
                                        "virtual_sdcard": None,
                                        "extruder": None,
                                        "heater_bed": None,
                                        "gcode_move": None,
                                    }
                                },
                            }
                        )
                    )
                    while True:
                        raw_message = await websocket.recv()
                        payload = json.loads(raw_message)
                        updates = _extract_moonraker_updates_from_ws(payload)
                        if updates:
                            await self._apply_ws_updates(printer_id, updates)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await self._set_connection_state(printer_id, connected=False, error=str(exc))
                await asyncio.sleep(MOONRAKER_WS_RECONNECT_DELAY_SECONDS)

    async def _set_connection_state(self, printer_id: str, *, connected: bool, error: str | None) -> None:
        now = datetime.now(timezone.utc)
        snapshot = dict(self._snapshots.get(printer_id) or {})
        snapshot["monitor_ws_connected"] = connected
        snapshot["monitor_ws_last_error"] = error
        if connected:
            snapshot["monitor_last_event_at"] = now
            snapshot["monitor_last_seen_at"] = now
        self._snapshots[printer_id] = snapshot
        await self._persist_updates(printer_id, {
            "monitor_ws_connected": connected,
            "monitor_ws_last_error": error,
            "monitor_last_updated_at": now,
            **({"monitor_last_seen_at": now} if connected else {}),
        })

    async def _apply_ws_updates(self, printer_id: str, updates: dict[str, Any]) -> None:
        snapshot = dict(self._snapshots.get(printer_id) or {})
        snapshot.update(updates)
        self._snapshots[printer_id] = snapshot
        await self._persist_updates(printer_id, updates)

    async def _persist_updates(self, printer_id: str, updates: dict[str, Any]) -> None:
        async with async_session() as db:
            result = await db.execute(select(Printer).where(Printer.id == uuid.UUID(printer_id)))
            printer = result.scalar_one_or_none()
            if printer is None:
                return
            for field, value in updates.items():
                setattr(printer, field, value)
            await db.commit()


moonraker_websocket_manager = MoonrakerWebsocketManager()


async def _gather_octoprint_payloads(provider: OctoPrintMonitorProvider, printer: Printer) -> tuple[dict[str, Any], dict[str, Any]]:
    printer_payload = await provider._request(printer, "/api/printer")
    job_payload = await provider._request(printer, "/api/job")
    return printer_payload, job_payload


async def _gather_moonraker_payloads(
    provider: MoonrakerMonitorProvider, printer: Printer
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    server_payload = await provider._request(printer, "/server/info")
    printer_payload = await provider._request(printer, "/printer/info")
    objects_payload = await provider._request(
        printer,
        "/printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed&gcode_move",
    )
    return server_payload, printer_payload, objects_payload


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_tool_actual(temp_payload: dict[str, Any]) -> float | None:
    for key in ("tool0", "tool1"):
        value = (temp_payload.get(key) or {}).get("actual")
        if value is not None:
            return _to_float(value)
    return None


def _extract_tool_target(temp_payload: dict[str, Any]) -> float | None:
    for key in ("tool0", "tool1"):
        value = (temp_payload.get(key) or {}).get("target")
        if value is not None:
            return _to_float(value)
    return None


def _extract_filename_from_path(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    normalized = value.rstrip("/")
    if not normalized:
        return None
    return normalized.rsplit("/", 1)[-1] or None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return None


def _build_moonraker_state_from_poll(
    server_payload: dict[str, Any],
    printer_payload: dict[str, Any],
    objects_payload: dict[str, Any],
) -> dict[str, Any]:
    provider = MoonrakerMonitorProvider()
    server_info = server_payload.get("result") or {}
    printer_info = printer_payload.get("result") or {}
    status = (objects_payload.get("result") or {}).get("status") or {}
    return _build_moonraker_updates(
        provider=provider,
        server_state=server_info.get("klippy_state"),
        printer_state=printer_info.get("state"),
        printer_state_message=printer_info.get("state_message"),
        status=status,
        event_type="poll",
        event_time=datetime.now(timezone.utc),
        ws_connected=None,
        ws_error=None,
    )


def _extract_moonraker_updates_from_ws(payload: dict[str, Any]) -> dict[str, Any] | None:
    method = payload.get("method")
    if method not in {"notify_status_update", "notify_history_changed", "notify_klippy_shutdown", "notify_klippy_ready", "notify_klippy_disconnected"}:
        return None

    if method == "notify_status_update":
        params = payload.get("params") or []
        status_patch = params[0] if params else {}
        event_time = _coerce_datetime(params[1]) or datetime.now(timezone.utc)
        return _build_moonraker_updates(
            provider=MoonrakerMonitorProvider(),
            server_state=None,
            printer_state=None,
            printer_state_message=None,
            status=status_patch,
            event_type=method,
            event_time=event_time,
            ws_connected=True,
            ws_error=None,
        )

    event_time = datetime.now(timezone.utc)
    status_patch: dict[str, Any] = {}
    if method == "notify_klippy_shutdown":
        status_patch = {"print_stats": {"state": "error", "message": "Klippy shutdown"}}
    elif method == "notify_klippy_disconnected":
        status_patch = {"print_stats": {"state": "standby", "message": "Klippy disconnected"}}
    elif method == "notify_klippy_ready":
        status_patch = {"print_stats": {"state": "standby", "message": "Klippy ready"}}

    return _build_moonraker_updates(
        provider=MoonrakerMonitorProvider(),
        server_state=None,
        printer_state=None,
        printer_state_message=None,
        status=status_patch,
        event_type=method,
        event_time=event_time,
        ws_connected=True,
        ws_error=None,
    )


def _build_moonraker_updates(
    *,
    provider: MoonrakerMonitorProvider,
    server_state: str | None,
    printer_state: str | None,
    printer_state_message: str | None,
    status: dict[str, Any],
    event_type: str,
    event_time: datetime,
    ws_connected: bool | None,
    ws_error: str | None,
) -> dict[str, Any]:
    print_stats = status.get("print_stats") or {}
    virtual_sdcard = status.get("virtual_sdcard") or {}
    extruder = status.get("extruder") or {}
    heater_bed = status.get("heater_bed") or {}
    gcode_move = status.get("gcode_move") or {}
    info = status.get("info") or {}

    normalized_status, online = provider._normalize_status(
        server_state=server_state,
        printer_state=printer_state,
        print_state=print_stats.get("state"),
        sdcard_active=virtual_sdcard.get("is_active"),
    )

    progress = _to_float(virtual_sdcard.get("progress"))
    completion = None if progress is None else round(progress * 100, 2)
    file_name = print_stats.get("filename") or _extract_filename_from_path(virtual_sdcard.get("file_path"))
    message = (
        print_stats.get("message")
        or info.get("state_message")
        or printer_state_message
        or print_stats.get("state")
        or server_state
        or printer_state
    )

    total_duration = _to_float(print_stats.get("total_duration"))
    print_duration = _to_float(print_stats.get("print_duration"))
    estimated_total_duration = _to_float(print_stats.get("estimated_time"))
    remaining_seconds = _to_float(print_stats.get("remaining_time"))
    if remaining_seconds is None and estimated_total_duration is not None and print_duration is not None:
        remaining_seconds = max(estimated_total_duration - print_duration, 0.0)
    elif remaining_seconds is None and progress and print_duration is not None:
        estimated_runtime = print_duration / progress if progress > 0 else None
        if estimated_runtime is not None:
            remaining_seconds = max(estimated_runtime - print_duration, 0.0)
    elif remaining_seconds is None and progress and total_duration is not None:
        estimated_runtime = total_duration / progress if progress > 0 else None
        if estimated_runtime is not None:
            remaining_seconds = max(estimated_runtime - total_duration, 0.0)

    elapsed_seconds = print_duration if print_duration is not None else total_duration
    eta_at = None if remaining_seconds is None else event_time + timedelta(seconds=remaining_seconds)

    current_layer = _to_int(print_stats.get("info", {}).get("current_layer") or print_stats.get("current_layer") or info.get("current_layer"))
    total_layers = _to_int(print_stats.get("info", {}).get("total_layer") or print_stats.get("info", {}).get("total_layers") or print_stats.get("total_layer") or print_stats.get("total_layers") or info.get("total_layer") or info.get("total_layers"))
    if current_layer is None:
        current_layer = _to_int(gcode_move.get("layer"))

    updates = {
        "monitor_online": online,
        "status": normalized_status,
        "monitor_status": normalized_status,
        "monitor_progress_percent": completion,
        "current_print_name": file_name,
        "monitor_last_message": message,
        "monitor_bed_temp_c": _to_float(heater_bed.get("temperature")),
        "monitor_tool_temp_c": _to_float(extruder.get("temperature")),
        "monitor_bed_target_c": _to_float(heater_bed.get("target")),
        "monitor_tool_target_c": _to_float(extruder.get("target")),
        "monitor_current_layer": current_layer,
        "monitor_total_layers": total_layers,
        "monitor_elapsed_seconds": elapsed_seconds,
        "monitor_remaining_seconds": remaining_seconds,
        "monitor_eta_at": eta_at,
        "monitor_last_seen_at": event_time,
        "monitor_last_updated_at": event_time,
        "monitor_last_error": None,
        "monitor_last_event_type": event_type,
        "monitor_last_event_at": event_time,
    }
    if ws_connected is not None:
        updates["monitor_ws_connected"] = ws_connected
    if ws_error is not None or ws_connected is not None:
        updates["monitor_ws_last_error"] = ws_error
    return updates


def _build_moonraker_websocket_url(base_url: str, api_key: str | None) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    query = dict(parse_qsl(parsed.query))
    if api_key:
        query["token"] = api_key
    return urlunparse((scheme, parsed.netloc, "/websocket", "", urlencode(query), ""))


def _snapshot_is_fresh(snapshot: dict[str, Any]) -> bool:
    if not snapshot.get("monitor_ws_connected"):
        return False
    last_event_at = _coerce_datetime(snapshot.get("monitor_last_event_at")) or _coerce_datetime(snapshot.get("monitor_last_seen_at"))
    if last_event_at is None:
        return False
    return datetime.now(timezone.utc) - last_event_at <= timedelta(seconds=MOONRAKER_WS_STALE_AFTER_SECONDS)


def get_provider(printer: Printer) -> PrinterMonitorProvider:
    provider = (printer.monitor_provider or "").strip().lower()
    if provider == "octoprint":
        return OctoPrintMonitorProvider()
    if provider == "moonraker":
        return MoonrakerMonitorProvider()
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
        if printer.monitor_provider == "moonraker":
            printer.monitor_ws_connected = False
            printer.monitor_ws_last_error = str(exc)
    await db.commit()
    await db.refresh(printer)
    return printer


def _should_refresh(printer: Printer) -> bool:
    if printer.monitor_provider == "moonraker" and printer.monitor_ws_connected:
        last_event_at = printer.monitor_last_event_at or printer.monitor_last_seen_at
        if last_event_at and datetime.now(timezone.utc) - last_event_at <= timedelta(seconds=MOONRAKER_WS_STALE_AFTER_SECONDS):
            return False
    interval = max(5, printer.monitor_poll_interval_seconds or 30)
    if printer.monitor_last_updated_at is None:
        return True
    return datetime.now(timezone.utc) - printer.monitor_last_updated_at >= timedelta(seconds=interval)


def mark_printer_stale_if_needed(printer: Printer) -> Printer:
    if not printer.monitor_enabled:
        return printer
    if printer.monitor_provider == "moonraker" and printer.monitor_last_event_at:
        if datetime.now(timezone.utc) - printer.monitor_last_event_at > timedelta(seconds=MOONRAKER_WS_STALE_AFTER_SECONDS):
            printer.monitor_ws_connected = False
    if printer.monitor_last_seen_at is None:
        return printer
    stale_after = timedelta(minutes=DEFAULT_STALE_AFTER_MINUTES)
    if datetime.now(timezone.utc) - printer.monitor_last_seen_at > stale_after:
        printer.monitor_online = False
        printer.monitor_status = "offline"
        printer.status = "offline"
    return printer
