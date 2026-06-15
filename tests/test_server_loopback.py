from __future__ import annotations

from fastapi.testclient import TestClient

from kitchen_display_server.server import create_app


def test_non_loopback_post_image_rejected(tmp_config):
    app = create_app(tmp_config, allow_test_loopback=False)
    client = TestClient(app)
    r = client.post("/api/v1/image", content=b"BM" + b"\x00" * 100)
    assert r.status_code == 403
    assert "loopback" in r.json()["detail"]


def test_non_loopback_delete_image_rejected(tmp_config):
    app = create_app(tmp_config, allow_test_loopback=False)
    client = TestClient(app)
    r = client.delete("/api/v1/image")
    assert r.status_code == 403
