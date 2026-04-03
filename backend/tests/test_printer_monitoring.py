from __future__ import annotations

import pytest

from app.models.printer import Printer
from datetime import datetime, timezone

from app.services.printer_monitoring import (
    MoonrakerMonitorProvider,
    OctoPrintMonitorProvider,
    _build_moonraker_thumbnail_file_path,
    _detect_embedded_media_type,
    _extract_moonraker_updates_from_ws,
    _normalize_relative_thumbnail_path,
    _parse_gcode_embedded_thumbnails,
    _select_best_embedded_thumbnail,
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
        if path == "/server/files/metadata?filename=demo.gcode":
            return {"result": {"filename": "demo.gcode", "thumbnails": []}}
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


@pytest.mark.asyncio
async def test_moonraker_fetch_live_state_includes_thumbnail_metadata(monkeypatch):
    provider = MoonrakerMonitorProvider()
    printer = Printer(
        name="Unicode",
        slug="unicode",
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
                            "filename": "prints/猫 テスト.gcode",
                            "state": "printing",
                        },
                        "virtual_sdcard": {"progress": 0.5, "is_active": True},
                    }
                }
            }
        if path == "/server/files/metadata?filename=prints%2F%E7%8C%AB%20%E3%83%86%E3%82%B9%E3%83%88.gcode":
            return {
                "result": {
                    "filename": "prints/猫 テスト.gcode",
                    "thumbnails": [
                        {"relative_path": ".thumbs/猫 テスト-32x32.png", "width": 32, "height": 32, "size": 100},
                        {"relative_path": ".thumbs/猫 テスト-300x300.png", "width": 300, "height": 300, "size": 999},
                    ],
                }
            }
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(provider, "_request", fake_request)

    result = await provider.fetch_live_state(printer)

    assert result["current_print_thumbnail_path"] == "prints/.thumbs/猫 テスト-300x300.png"
    assert len(result["current_print_thumbnails"]) == 2
    assert result["current_print_thumbnails"][0]["relative_path"] == "prints/.thumbs/猫 テスト-32x32.png"


def test_thumbnail_path_helpers_handle_relative_and_unicode_paths():
    relative = _normalize_relative_thumbnail_path("folder/猫 テスト.gcode", ".thumbs/猫 テスト-300x300.png")
    parent_relative = _normalize_relative_thumbnail_path("folder/sub/猫 テスト.gcode", "../.thumbs/preview.png")
    encoded = _build_moonraker_thumbnail_file_path("folder/.thumbs/猫 テスト-300x300.png")

    assert relative == "folder/.thumbs/猫 テスト-300x300.png"
    assert parent_relative == "folder/.thumbs/preview.png"
    assert encoded == "/server/files/gcodes/folder/.thumbs/%E7%8C%AB%20%E3%83%86%E3%82%B9%E3%83%88-300x300.png"


@pytest.mark.asyncio
async def test_printer_thumbnail_endpoint_proxies_moonraker_file(client, auth_headers, db_session, monkeypatch):
    printer = Printer(
        name="Lava",
        slug="lava",
        monitor_enabled=True,
        monitor_provider="moonraker",
        monitor_base_url="http://printer.local:7125",
    )
    db_session.add(printer)
    await db_session.commit()
    await db_session.refresh(printer)

    async def fake_fetch_current_thumbnail(self, printer_arg):
        assert printer_arg.id == printer.id
        return type("Thumb", (), {"content": b"png-bytes", "media_type": "image/png"})()

    monkeypatch.setattr(MoonrakerMonitorProvider, "fetch_current_thumbnail", fake_fetch_current_thumbnail)

    response = await client.get(f"/api/v1/printers/{printer.id}/thumbnail", headers=auth_headers)

    assert response.status_code == 200
    assert response.content == b"png-bytes"
    assert response.headers["content-type"].startswith("image/png")


# ---------------------------------------------------------------------------
# Embedded gcode thumbnail parsing tests
# ---------------------------------------------------------------------------

import base64


def _make_gcode_header(width: int, height: int, png_bytes: bytes) -> str:
    """Build a minimal gcode header with an embedded thumbnail block."""
    b64 = base64.b64encode(png_bytes).decode()
    # Split into 78-char lines like real slicers do
    lines = [b64[i : i + 78] for i in range(0, len(b64), 78)]
    block = [f"; thumbnail begin {width}x{height} {len(png_bytes)}"]
    block.extend(f"; {line}" for line in lines)
    block.append("; thumbnail end")
    return "\n".join(
        [
            "; generated by TestSlicer",
            *block,
            ";",
            "G28 ; Home all axes",
        ]
    )


# A minimal valid 1x1 PNG (67 bytes)
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_parse_gcode_embedded_thumbnails_single():
    header = _make_gcode_header(300, 300, _TINY_PNG)
    thumbnails = _parse_gcode_embedded_thumbnails(header)
    assert len(thumbnails) == 1
    assert thumbnails[0].width == 300
    assert thumbnails[0].height == 300
    assert thumbnails[0].data == _TINY_PNG


def test_parse_gcode_embedded_thumbnails_multiple_selects_largest():
    small = _make_gcode_header(32, 32, b"\x89PNG small")
    large = _make_gcode_header(300, 300, _TINY_PNG)
    # Combine both blocks
    combined = small + "\n" + large
    thumbnails = _parse_gcode_embedded_thumbnails(combined)
    assert len(thumbnails) == 2
    best = _select_best_embedded_thumbnail(thumbnails)
    assert best is not None
    assert best.width == 300
    assert best.height == 300


def test_parse_gcode_embedded_thumbnails_empty_when_no_marker():
    gcode = "; no thumbnail here\nG28\nG1 X10 Y10\n"
    thumbnails = _parse_gcode_embedded_thumbnails(gcode)
    assert thumbnails == []


def test_detect_embedded_media_type_png():
    assert _detect_embedded_media_type(_TINY_PNG) == "image/png"


def test_detect_embedded_media_type_jpeg():
    assert _detect_embedded_media_type(b"\xff\xd8\xff\xe0fake") == "image/jpeg"


def test_detect_embedded_media_type_fallback():
    assert _detect_embedded_media_type(b"\x00\x00\x00\x00") == "image/png"


@pytest.mark.asyncio
async def test_fetch_current_thumbnail_falls_back_to_embedded(monkeypatch):
    """When metadata has no thumbnails, fetch_current_thumbnail reads the gcode header."""
    provider = MoonrakerMonitorProvider()
    printer = Printer(
        name="K2 Pro",
        slug="k2pro",
        monitor_provider="moonraker",
        monitor_base_url="http://10.0.1.51:7125",
    )

    gcode_header = _make_gcode_header(300, 300, _TINY_PNG)

    async def fake_live_state(_printer):
        # Simulates Creality K2 Pro: printing but no thumbnail in metadata
        return {
            "current_print_name": "Object_1_PLA_2h51m45s.gcode",
            "current_print_thumbnail_path": None,
        }

    async def fake_partial_text(_printer, path, max_bytes):
        assert "Object_1_PLA_2h51m45s.gcode" in path
        return gcode_header

    monkeypatch.setattr(provider, "fetch_live_state", fake_live_state)
    monkeypatch.setattr(provider, "_request_partial_text", fake_partial_text)

    result = await provider.fetch_current_thumbnail(printer)

    assert result is not None
    assert result.content == _TINY_PNG
    assert result.media_type == "image/png"
    assert "embedded://" in result.path


@pytest.mark.asyncio
async def test_fetch_current_thumbnail_prefers_metadata_over_embedded(monkeypatch):
    """When metadata has thumbnails, the embedded fallback is NOT used."""
    provider = MoonrakerMonitorProvider()
    printer = Printer(
        name="Standard",
        slug="standard",
        monitor_provider="moonraker",
        monitor_base_url="http://printer.local:7125",
    )

    async def fake_live_state(_printer):
        return {
            "current_print_name": "test.gcode",
            "current_print_thumbnail_path": ".thumbs/test-300x300.png",
        }

    async def fake_request_bytes(_printer, path):
        return (b"standard-png-bytes", "image/png")

    monkeypatch.setattr(provider, "fetch_live_state", fake_live_state)
    monkeypatch.setattr(provider, "_request_bytes", fake_request_bytes)

    result = await provider.fetch_current_thumbnail(printer)

    assert result is not None
    assert result.content == b"standard-png-bytes"
    assert "embedded://" not in result.path
