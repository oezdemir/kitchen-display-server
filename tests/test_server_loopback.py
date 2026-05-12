from __future__ import annotations

from fastapi.testclient import TestClient

from xte_kitchen_server.config import Config
from xte_kitchen_server.server import create_app


def test_non_loopback_post_image_rejected(tmp_path, monkeypatch):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "device.token").write_text("t")
    monkeypatch.setenv("XTE_KITCHEN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("XTE_KITCHEN_SECRETS_DIR", str(secrets))
    cfg = Config.from_env()
    app = create_app(cfg, allow_test_loopback=False)
    client = TestClient(app)
    r = client.post("/api/v1/image", content=b"BM" + b"\x00" * 100)
    assert r.status_code == 403
    assert "loopback" in r.json()["detail"]


def test_non_loopback_delete_image_rejected(tmp_path, monkeypatch):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "device.token").write_text("t")
    monkeypatch.setenv("XTE_KITCHEN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("XTE_KITCHEN_SECRETS_DIR", str(secrets))
    cfg = Config.from_env()
    app = create_app(cfg, allow_test_loopback=False)
    client = TestClient(app)
    r = client.delete("/api/v1/image")
    assert r.status_code == 403
