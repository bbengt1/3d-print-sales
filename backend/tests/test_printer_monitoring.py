from __future__ import annotations

import pytest

from app.models.printer import Printer
from datetime import datetime, timezone

from app.services.printer_monitoring import (
    MoonrakerMonitorProvider,
    OctoPrintMonitorProvider,
    _extract_moonraker_updates_from_ws,
    get_provider,
)


def test_get_provider_supports_moonraker_and_octoprint():
    moonraker_printer = Printer(name="Moonraker", slug="moonraker", monitor_provider="moonraker")
    octoprint_printer = Printer(name="OctoPrint", slug="octoprint", monitor_provider="octoprint")

    assert isinstance(get_provider(moonraker_printer), MoonrakerMonitorProvider)
    assert isinstance(get_provider(octoprint_printer), OctoPrintMonitorProvider)


@pytest.mark.asyncio
async def test_moonraker_fetch_live_state_normalizes_printing(monkeypatch):
    provider = MoonrakerMonitorProvider()
    printer = Printer(
        name="Lava",
        slug="lava",
        monitor_provider="moonraker",
        monitor_base_url="http://printer.local:7125",
    )

    async def fake_request(_printer, path):
        if path == "/server/info":
            return {"result": {"klippy_state": "ready", "moonraker_version": "1.2.0"}}
        if path == "/printer/info":
            return {"result": {"state": "ready", "state_message": "Printer is ready"}}
        if path == "/printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed&gcode_move":
            return {
                "result": {
                    "status": {
                        "print_stats": {
                            "filename": "demo.gcode",
                            "state": "printing",
                            "message": "Layer change",
                            "print_duration": 600,
                            "total_duration": 720,
                            "info": {"current_layer": 12, "total_layer": 120},
                        },
                        "virtual_sdcard": {
                            "progress": 0.5,
                            "is_active": True,
                            "file_path": "/home/pi/printer_data/gcodes/demo.gcode",
                        },
                        "extruder": {"temperature": 215.2, "target": 220},
                        "heater_bed": {"temperature": 60.4, "target": 65},
                        "gcode_move": {"layer": 12},
                    }
                }
            }
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(provider, "_request", fake_request)

    result = await provider.fetch_live_state(printer)

    assert result["status"] == "printing"
    assert result["monitor_status"] == "printing"
    assert result["monitor_online"] is True
    assert result["monitor_progress_percent"] == 50.0
    assert result["current_print_name"] == "demo.gcode"
    assert result["monitor_tool_temp_c"] == 215.2
    assert result["monitor_bed_temp_c"] == 60.4
    assert result["monitor_tool_target_c"] == 220.0
    assert result["monitor_bed_target_c"] == 65.0
    assert result["monitor_current_layer"] == 12
    assert result["monitor_total_layers"] == 120
    assert result["monitor_elapsed_seconds"] == 600.0
    assert result["monitor_remaining_seconds"] == 600.0
    assert result["monitor_last_event_type"] == "poll"
    assert result["monitor_last_error"] is None


@pytest.mark.asyncio
async def test_moonraker_test_connection_returns_idle(monkeypatch):
    provider = MoonrakerMonitorProvider()
    printer = Printer(
        name="Lava",
        slug="lava",
        monitor_provider="moonraker",
        monitor_base_url="http://printer.local:7125",
    )

    async def fake_request(_printer, path):
        if path == "/server/info":
            return {"result": {"klippy_state": "ready", "moonraker_version": "1.2.0"}}
        if path == "/printer/info":
            return {"result": {"state": "ready", "state_message": "Printer is ready"}}
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(provider, "_request", fake_request)

    result = await provider.test_connection(printer)

    assert result.ok is True
    assert result.provider == "moonraker"
    assert result.normalized_status == "idle"
    assert result.online is True
    assert result.message == "Printer is ready"


def test_extract_moonraker_updates_from_websocket_event():
    event_time = datetime.now(timezone.utc).timestamp()
    updates = _extract_moonraker_updates_from_ws(
        {
            "method": "notify_status_update",
            "params": [
                {
                    "print_stats": {
                        "state": "printing",
                        "filename": "ws-demo.gcode",
                        "print_duration": 300,
                        "remaining_time": 900,
                        "info": {"current_layer": 5, "total_layer": 50},
                    },
                    "virtual_sdcard": {"progress": 0.25, "is_active": True},
                    "extruder": {"temperature": 210.5, "target": 215},
                    "heater_bed": {"temperature": 59.8, "target": 60},
                },
                event_time,
            ],
        }
    )

    assert updates is not None
    assert updates["status"] == "printing"
    assert updates["monitor_ws_connected"] is True
    assert updates["monitor_progress_percent"] == 25.0
    assert updates["monitor_current_layer"] == 5
    assert updates["monitor_total_layers"] == 50
    assert updates["monitor_remaining_seconds"] == 900.0
    assert updates["monitor_tool_target_c"] == 215.0
    assert updates["monitor_last_event_type"] == "notify_status_update"
