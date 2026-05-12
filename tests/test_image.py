from __future__ import annotations

import io

import pytest
from PIL import Image

from tests.helpers import make_bmp, make_png
from xte_kitchen_server.image import (
    ImageValidationError,
    convert_png_to_bmp,
    detect_format,
    validate_bmp,
)


def test_detect_format_bmp():
    assert detect_format(make_bmp()) == "bmp"


def test_detect_format_png():
    assert detect_format(make_png()) == "png"


def test_detect_format_unknown():
    assert detect_format(b"this is not an image") == "unknown"


def test_detect_format_short_payload():
    assert detect_format(b"B") == "unknown"


@pytest.mark.parametrize("mode", ["1", "L", "RGB"])
def test_validate_bmp_accepts_supported_modes(mode):
    payload = make_bmp(mode=mode)
    assert validate_bmp(payload) == payload


def test_validate_bmp_rejects_wrong_width():
    payload = make_bmp(width=799)
    with pytest.raises(ImageValidationError, match="dimensions"):
        validate_bmp(payload)


def test_validate_bmp_rejects_wrong_height():
    payload = make_bmp(height=479)
    with pytest.raises(ImageValidationError, match="dimensions"):
        validate_bmp(payload)


def test_validate_bmp_rejects_non_bmp_bytes():
    with pytest.raises(ImageValidationError, match="not a BMP"):
        validate_bmp(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)


def test_convert_png_to_bmp_produces_1bit_800x480():
    png = make_png()
    bmp = convert_png_to_bmp(png)
    # Re-open with Pillow to confirm shape and depth
    img = Image.open(io.BytesIO(bmp))
    assert img.format == "BMP"
    assert img.size == (800, 480)
    assert img.mode == "1"


def test_convert_png_rejects_wrong_size():
    png = make_png(width=400, height=400)
    with pytest.raises(ImageValidationError, match="dimensions"):
        convert_png_to_bmp(png)
