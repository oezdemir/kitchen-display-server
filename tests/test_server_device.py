from __future__ import annotations


def test_device_401_no_auth_header(client):
    r = client.get("/api/v1/sleep.bmp")
    assert r.status_code == 401


def test_device_401_bad_token(client):
    r = client.get("/api/v1/sleep.bmp", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_device_503_when_no_image(client, auth_headers):
    r = client.get("/api/v1/sleep.bmp", headers=auth_headers)
    assert r.status_code == 503
