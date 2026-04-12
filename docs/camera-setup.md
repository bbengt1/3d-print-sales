# Camera Setup Guide

Live camera feeds for printer monitoring, powered by go2rtc.

## Overview

Cameras are standalone devices (e.g., Wyze Cam v4) that watch printers. Each camera is configured as its own entity in the app and can be assigned to exactly one printer. The browser connects directly to go2rtc for low-latency MSE/WebSocket streaming with an MJPEG snapshot fallback proxied through the backend.

## Prerequisites

- **go2rtc** running on your network, accessible from both the app server and client browsers
- Camera sources configured in go2rtc (e.g., Wyze cameras via native P2P, RTSP, or other supported protocols)
- The 3D Print Sales app deployed and running

## go2rtc Configuration

Example `go2rtc.yaml` for three Wyze cameras:

```yaml
streams:
  wyze_printer_1:
    - wyze://user@example.com:password#DeviceName1
  wyze_printer_2:
    - wyze://user@example.com:password#DeviceName2
  wyze_printer_3:
    - wyze://user@example.com:password#DeviceName3
```

Once go2rtc is running, verify streams are available at `http://<go2rtc-host>:1984/api/streams`.

## Adding Cameras in the App

1. Navigate to **Admin > Cameras** in the app
2. Click **Add Camera**
3. Fill in:
   - **Name**: A human-readable label (e.g., "Wyze Cam - Bay 1")
   - **Slug**: Auto-generated from name, or customized
   - **go2rtc Base URL**: The base URL of your go2rtc instance (e.g., `http://192.168.1.50:1984`)
   - **Stream Name**: The stream name from your go2rtc config (e.g., `wyze_printer_1`)
4. Optionally assign to a printer using the dropdown
5. Click **Add Camera**

A live snapshot preview appears in the form when the URL and stream name are filled in correctly.

## Assigning Cameras to Printers

Each camera can be assigned to exactly one printer. Assignment can be done:

- During camera creation (printer dropdown in the form)
- By editing an existing camera
- Via the API: `POST /api/v1/cameras/{id}/assign` with `{ "printer_id": "<uuid>" }`

Once assigned, the camera feed appears:

- On the **printer wall card** (replaces the print thumbnail)
- In the **printer detail page** (Visual Console section)
- On the **dedicated monitor page** (`/print-floor/monitor/{printer-id}`)

## Stream Formats

The app supports two streaming methods:

| Method | URL Pattern | Latency | Browser Support |
|--------|-------------|---------|-----------------|
| **MSE** (primary) | `ws://{host}/api/ws?src={stream}` | Sub-second | Chrome, Edge, Firefox |
| **MJPEG** (fallback) | `{host}/api/frame.jpeg?src={stream}` | ~2 seconds | All browsers |

MSE streaming is used by default. If the WebSocket connection fails or MediaSource is unavailable (e.g., Safari), the app automatically falls back to MJPEG snapshot polling through the backend proxy.

## Monitor / Kiosk Mode

For wall-mounted displays or dedicated monitoring stations, use the kiosk URL:

```
https://your-app.local/print-floor/monitor/{printer-id}
```

This provides:
- Full-screen camera feed with no navigation chrome
- Translucent telemetry overlay (printer name, status, progress, temps)
- Auto-refresh of printer data every 30 seconds
- "Exit Monitor" button to return to printer detail

## Troubleshooting

### Camera shows "Connecting..." but never goes live

- Verify go2rtc is accessible from the browser (not just the server)
- Check that the stream name matches exactly what's in `go2rtc.yaml`
- Open the go2rtc web UI at `http://<host>:1984` to verify the stream is active

### Snapshot proxy returns 502

- The backend cannot reach the go2rtc instance
- Check network connectivity between the app server and go2rtc host
- Verify the go2rtc base URL is correct (no trailing slash)

### CORS errors in browser console

- go2rtc serves CORS headers by default
- If go2rtc is behind a reverse proxy, ensure the proxy forwards WebSocket upgrade headers and CORS headers

### Camera feed freezes after a while

- The app cleans up video buffers every 10 seconds (keeps last 30 seconds)
- If still freezing, check go2rtc memory usage and stream health
- The tab visibility API pauses streams when the tab is hidden and reconnects when visible

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cameras` | GET | List cameras (filters: `is_active`, `assigned`, `search`) |
| `/api/v1/cameras` | POST | Create camera |
| `/api/v1/cameras/{id}` | GET | Get camera |
| `/api/v1/cameras/{id}` | PUT | Update camera |
| `/api/v1/cameras/{id}` | DELETE | Soft-delete camera |
| `/api/v1/cameras/{id}/assign` | POST | Assign/unassign printer |
| `/api/v1/cameras/{id}/snapshot` | GET | Proxy MJPEG snapshot from go2rtc |
