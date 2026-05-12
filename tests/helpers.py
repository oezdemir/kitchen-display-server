"""Shared test fixtures for producing valid BMP/PNG payloads."""

from __future__ import annotations

import io

from PIL import Image


def make_bmp(width: int = 800, height: int = 480, mode: str = "1") -> bytes:
    """Return uncompressed BMP bytes of the given size/mode."""
    fill: object
    if mode == "1":
        fill = 1
    elif mode == "RGBA":
        fill = (255, 255, 255, 255)
    elif mode == "RGB":
        fill = (255, 255, 255)
    else:
        fill = 255
    img = Image.new(mode, (width, height), fill)
    if mode == "P":
        # Image.new("P") produces no palette; attach a grayscale one so the
        # BMP round-trips cleanly through Pillow's BMP decoder.
        img.putpalette(list(range(256)) * 3)
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    return buf.getvalue()


def make_png(width: int = 800, height: int = 480) -> bytes:
    img = Image.new("L", (width, height), 200)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
