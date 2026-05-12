from __future__ import annotations

from helpers import make_bmp

from xte_kitchen_server.storage import Storage, compute_etag


def test_device_401_no_auth_header(client):
    r = client.get("/api/v1/sleep.bmp")
    assert r.status_code == 401


def test_device_401_bad_token(client):
    r = client.get("/api/v1/sleep.bmp", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_device_503_when_no_image(client, auth_headers):
    r = client.get("/api/v1/sleep.bmp", headers=auth_headers)
    assert r.status_code == 503


def test_device_200_returns_gzipped_bmp_with_etag(client, auth_headers, tmp_config):
    bmp = make_bmp()
    Storage(tmp_config.state_dir).write_image(bmp)
    r = client.get("/api/v1/sleep.bmp", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/bmp"
    assert r.headers["content-encoding"] == "gzip"
    assert r.headers["etag"] == compute_etag(bmp)
    assert r.content == bmp  # httpx auto-decompressed the gzipped response


def test_device_304_round_trip_preserves_etag(client, auth_headers, tmp_config):
    bmp = make_bmp()
    Storage(tmp_config.state_dir).write_image(bmp)
    etag = compute_etag(bmp)
    r = client.get(
        "/api/v1/sleep.bmp",
        headers={**auth_headers, "If-None-Match": etag},
    )
    assert r.status_code == 304
    assert r.headers["etag"] == etag
    assert r.content == b""


def test_device_telemetry_captured(client, auth_headers, tmp_config):
    Storage(tmp_config.state_dir).write_image(make_bmp())
    client.get(
        "/api/v1/sleep.bmp",
        headers={
            **auth_headers,
            "User-Agent": "CrossPoint-ESP32-1.2.3-kitchen",
            "X-Battery-Pct": "87",
        },
    )
    state = Storage(tmp_config.state_dir).read_device_state()
    assert state["last_battery_pct"] == 87
    assert state["last_user_agent"] == "CrossPoint-ESP32-1.2.3-kitchen"
    assert state["recent"][0]["status"] == 200
