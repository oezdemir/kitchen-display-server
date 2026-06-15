---
name: kitchen
description: Update the Seeed reTerminal E1001 kitchen e-ink display — push an 800x480 image (PNG or BMP), clear it, or check device status/battery. Use when asked to change what the kitchen display shows.
version: 0.1.0
---

# kitchen — update the family kitchen display

`kitchen` is a command on your PATH. It reaches a host-side service (through the
skill-gateway) that the Seeed reTerminal E1001 e-ink display polls on its own schedule. You
push to the service; the device picks up the new image the next time it wakes
(typically within ~30 min, or immediately if someone presses its refresh button).

The display is **800x480, 1-bit (black/white)**. You may push a PNG (any mode —
the host dithers it to 1-bit) or a ready-made 1-bit BMP.

## Commands

### `kitchen set-image - < FILE`
Upload an image. **The image is read from stdin**, so pipe or redirect the file:

```bash
kitchen set-image - < /tmp/kitchen.png
cat /tmp/lunch.bmp | kitchen set-image -
```

Prints JSON (`etag`, `sha256`, `bytes_raw`, `bytes_gz`, `updated_at`) on success.
The image should be 800x480; PNGs are dithered to 1-bit automatically.

### `kitchen clear`
Remove the current image. The device falls back to its on-device default after
its stale timeout.

### `kitchen status`
Show the current image's metadata and the latest device telemetry (when the
device last polled, battery %, user agent).

### `kitchen --help`
Show live CLI usage.

## When to use
- The user asks to update / change the kitchen display.
- You've rendered a new 800x480 image to show.
- The user asks about the display device's status or battery.

## When not to use
- Questions about the device *firmware* or its wake *schedule* — those are
  device-side settings, not controllable here.
- This pushes to the host service, not directly to the device; expect the
  display to update on the device's next wake, not instantly.
