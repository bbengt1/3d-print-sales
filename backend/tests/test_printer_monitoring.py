from __future__ import annotations

import pytest

from app.models.printer import Printer
from app.services.printer_monitoring import MoonrakerMonitorProvider, OctoPrintMonitorProvider, get_provider


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
        if path == "/printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed":
            return {
                "result": {
                    "status": {
                        "print_stats": {
                            "filename": "demo.gcode",
                            "state": "printing",
                            "message": "",
                        },
                        "virtual_sdcard": {
                            "progress": 0.5,
                            "is_active": True,
                            "file_path": "/home/pi/printer_data/gcodes/demo.gcode",
                        },
                        "extruder": {"temperature": 215.2},
                        "heater_bed": {"temperature": 60.4},
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
