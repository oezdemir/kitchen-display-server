from __future__ import annotations

import io

from helpers import make_bmp, make_png
from PIL import Image


def test_post_image_accepts_bmp_and_serves_it(client, tmp_config, auth_headers):
    bmp = make_bmp()
    r = client.post(
        "/api/v1/image", content=bmp,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["bytes_raw"] == len(bmp)
    assert body["bytes_gz"] > 0
    r2 = client.get("/api/v1/sleep.bmp", headers=auth_headers)
    assert r2.status_code == 200
    # httpx auto-decompresses; r2.content is the original BMP bytes
    assert r2.content == bmp


def test_post_image_accepts_png_and_converts_to_bmp(client, tmp_config, auth_headers):
    png = make_png()
    r = client.post(
        "/api/v1/image", content=png,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 200
    r2 = client.get("/api/v1/sleep.bmp", headers=auth_headers)
    assert r2.status_code == 200
    served_bmp = r2.content   # auto-decompressed
    img = Image.open(io.BytesIO(served_bmp))
    assert img.format == "BMP"
    assert img.size == (800, 480)
    assert img.mode == "1"


def test_post_image_415_on_garbage(client):
    r = client.post("/api/v1/image", content=b"this is not an image")
    assert r.status_code == 415


def test_post_image_422_on_wrong_dimensions(client):
    bad = make_bmp(width=400)
    r = client.post("/api/v1/image", content=bad)
    assert r.status_code == 422


def test_delete_image_clears_state(client, tmp_config, auth_headers):
    client.post("/api/v1/image", content=make_bmp())
    r = client.delete("/api/v1/image")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    r2 = client.get("/api/v1/sleep.bmp", headers=auth_headers)
    assert r2.status_code == 503


def test_get_state_shape(client, tmp_config, auth_headers):
    bmp = make_bmp()
    client.post("/api/v1/image", content=bmp)
    client.get("/api/v1/sleep.bmp", headers={**auth_headers, "X-Battery-Pct": "55"})
    r = client.get("/api/v1/state")
    assert r.status_code == 200
    body = r.json()
    assert body["current"]["bytes_raw"] == len(bmp)
    assert body["device"]["last_battery_pct"] == 55
    assert isinstance(body["device"]["recent"], list)
