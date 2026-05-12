"""Shared test fixtures for producing valid BMP/PNG payloads."""

from __future__ import annotations

import io

from PIL import Image


def make_bmp(width: int = 800, height: int = 480, mode: str = "1") -> bytes:
    """Return uncompressed BMP bytes of the given size/mode."""
    img = Image.new(mode, (width, height), 1 if mode == "1" else 255)
    buf = io.BytesIO()
    img.save(buf, format="BMP")
    return buf.getvalue()


def make_png(width: int = 800, height: int = 480) -> bytes:
    img = Image.new("L", (width, height), 200)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
