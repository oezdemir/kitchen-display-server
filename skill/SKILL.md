---
name: xte-kitchen
description: Push a rendered kitchen-display image (BMP or PNG) to the Xteink X4 and inspect device telemetry. Use when the agent needs to update what the e-ink kitchen display shows.
version: 0.1.0
---

# xte-kitchen — push images to the Xteink X4 kitchen display

This skill is a thin wrapper around the `xte-kitchen` CLI, installed
on PATH via `pipx install xte-kitchen-server`. The CLI talks to a
local FastAPI daemon (`hermes-xte-kitchen-server.service`, running
on port 8080) that the Xteink X4 polls on its own schedule.

The display is **pull-based**: the device fetches `/api/v1/sleep.bmp`
when it wakes (typically every 30 min or every 12 h). You do not push
to the device; you push to the daemon, and the device picks up the
new image the next time it wakes.

## Commands

### `xte-kitchen set-image <path>`

Upload an image to the daemon. Accepts:
- 800×480 BMP (1-, 4-, 8-, 24-, or 32-bit, uncompressed)
- 800×480 PNG (any mode) — server converts to 1-bit BMP with Floyd–Steinberg dithering

**Exit codes:**
- `0` — image accepted; prints JSON with `etag`, `sha256`, `bytes_raw`, `bytes_gz`
- non-zero — upload failed; stderr contains the HTTP status and reason

**Example:**

```bash
xte-kitchen set-image /tmp/kitchen.bmp
# {"etag": "\"abc123def4567890\"", "sha256": "...", "bytes_raw": 48054, "bytes_gz": 3120, "updated_at": "2026-05-11T08:30:01.234-07:00"}
```

### `xte-kitchen clear`

Remove the currently-stored image. The daemon returns 503 to the
device until the next `set-image`. After the device's stale-timeout
elapses, it falls back to the on-SD default image.

**Example:**

```bash
xte-kitchen clear
# {"ok": true}
```

### `xte-kitchen status`

Show current image metadata and the latest device telemetry. Use
this to inspect when the device last polled and what battery level
it reported.

**Output shape:**

```json
{
  "current": {
    "etag": "\"abc123def4567890\"",
    "sha256": "...",
    "bytes_raw": 48054,
    "bytes_gz": 3120,
    "updated_at": "2026-05-11T08:30:00.000-07:00"
  },
  "device": {
    "last_seen_at": "2026-05-11T08:35:01.234-07:00",
    "last_battery_pct": 87,
    "last_user_agent": "CrossPoint-ESP32-1.2.3-kitchen",
    "recent": [ /* up to 100 most-recent device queries */ ]
  }
}
```

Either top-level key may be `null` when no data exists yet.

## When to use this skill

- The user asks to update the kitchen display.
- The agent has rendered a new BMP/PNG that represents the next display state.
- The user asks about device status (last seen, battery level).
- Scheduled image refresh (the agent decides timing; this skill is the action).

## When **not** to use this skill

- The user is asking about the device firmware itself — this skill talks to the host, not the device.
- The user wants to remotely change the device's display schedule — that's a device-side setting (over the X4's web UI), not something this skill can do.
