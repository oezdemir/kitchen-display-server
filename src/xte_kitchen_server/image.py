"""Image format detection, BMP validation, and PNG → 1-bit BMP conversion."""

from __future__ import annotations

import io
from typing import Literal

from PIL import Image

EXPECTED_WIDTH = 800
EXPECTED_HEIGHT = 480

_BMP_MAGIC = b"BM"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Pillow modes that map to firmware-accepted bpp values {1, 8, 24, 32}.
# bpp-2 / bpp-4 BMPs decode to mode "P" via Pillow, so they're covered too.
_ACCEPTED_BMP_MODES = frozenset({"1", "L", "P", "RGB", "RGBA"})


class ImageValidationError(ValueError):
    """Raised when an input image fails the contract."""


def detect_format(data: bytes) -> Literal["bmp", "png", "unknown"]:
    if data.startswith(_BMP_MAGIC):
        return "bmp"
    if data.startswith(_PNG_MAGIC):
        return "png"
    return "unknown"


def validate_bmp(data: bytes) -> bytes:
    """Validate that `data` is a BMP we'll accept. Return the same bytes on success."""
    if not data.startswith(_BMP_MAGIC):
        raise ImageValidationError("payload is not a BMP (missing 'BM' magic)")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if img.format != "BMP":
                raise ImageValidationError(f"Pillow reports format {img.format}, not BMP")
            if img.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
                raise ImageValidationError(
                    f"BMP dimensions {img.size} != ({EXPECTED_WIDTH}, {EXPECTED_HEIGHT})"
                )
            if img.mode not in _ACCEPTED_BMP_MODES:
                raise ImageValidationError(f"Unsupported BMP mode {img.mode}")
    except ImageValidationError:
        raise
    except Exception as exc:
        raise ImageValidationError(f"BMP failed to parse: {exc}") from exc
    return data


def convert_png_to_bmp(data: bytes) -> bytes:
    """Convert PNG bytes to a 1-bit 800x480 BMP using Floyd–Steinberg dithering."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if img.format != "PNG":
                raise ImageValidationError(f"Pillow reports format {img.format}, not PNG")
            if img.size != (EXPECTED_WIDTH, EXPECTED_HEIGHT):
                raise ImageValidationError(
                    f"PNG dimensions {img.size} != ({EXPECTED_WIDTH}, {EXPECTED_HEIGHT})"
                )
            bw = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    except ImageValidationError:
        raise
    except Exception as exc:
        raise ImageValidationError(f"PNG failed to parse: {exc}") from exc

    buf = io.BytesIO()
    bw.save(buf, format="BMP")
    return buf.getvalue()
