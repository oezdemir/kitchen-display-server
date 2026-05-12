"""Image format detection, BMP validation, and PNG → 1-bit BMP conversion."""

from __future__ import annotations

import io
from typing import Literal

from PIL import Image

EXPECTED_WIDTH = 800
EXPECTED_HEIGHT = 480

BMP_MAGIC = b"BM"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class ImageValidationError(ValueError):
    """Raised when an input image fails the contract."""


def detect_format(data: bytes) -> Literal["bmp", "png", "unknown"]:
    if data.startswith(BMP_MAGIC):
        return "bmp"
    if data.startswith(PNG_MAGIC):
        return "png"
    return "unknown"


def validate_bmp(data: bytes) -> bytes:
    """Validate that `data` is a BMP we'll accept. Return the same bytes on success."""
    if not data.startswith(BMP_MAGIC):
        raise ImageValidationError("payload is not a BMP (missing 'BM' magic)")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ImageValidationError(f"BMP failed to parse: {exc}") from exc

    if img.format != "BMP":
        raise ImageValidationError(f"Pillow reports format {img.format}, not BMP")
    if img.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        raise ImageValidationError(
            f"BMP dimensions {img.size} != ({EXPECTED_WIDTH}, {EXPECTED_HEIGHT})"
        )
    if img.mode not in {"1", "L", "P", "RGB", "RGBA"}:
        raise ImageValidationError(f"Unsupported BMP mode {img.mode}")
    return data


def convert_png_to_bmp(data: bytes) -> bytes:
    """Convert PNG bytes to a 1-bit 800x480 BMP using Floyd–Steinberg dithering."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ImageValidationError(f"PNG failed to parse: {exc}") from exc

    if img.format != "PNG":
        raise ImageValidationError(f"Pillow reports format {img.format}, not PNG")
    if img.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
        raise ImageValidationError(
            f"PNG dimensions {img.size} != ({EXPECTED_WIDTH}, {EXPECTED_HEIGHT})"
        )

    bw = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    buf = io.BytesIO()
    bw.save(buf, format="BMP")
    return buf.getvalue()
