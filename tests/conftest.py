from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from xte_kitchen_server.config import Config
from xte_kitchen_server.server import create_app


@pytest.fixture
def tmp_config(tmp_path, monkeypatch) -> Config:
    state = tmp_path / "state"
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "device.token").write_text("test-token-abc123")
    for k in list(os.environ):
        if k.startswith("XTE_KITCHEN_"):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("XTE_KITCHEN_STATE_DIR", str(state))
    monkeypatch.setenv("XTE_KITCHEN_SECRETS_DIR", str(secrets))
    return Config.from_env()


@pytest.fixture
def app(tmp_config):
    return create_app(tmp_config, allow_test_loopback=True)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token-abc123"}
