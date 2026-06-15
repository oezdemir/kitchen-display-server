from __future__ import annotations

import os

import pytest

from kitchen_display_server.config import Config, TokenError


def _clear_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("KITCHEN_DISPLAY_"):
            monkeypatch.delenv(key, raising=False)


def test_config_defaults(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    # cwd anchors the default ./state and ./secrets paths under tmp_path.
    monkeypatch.chdir(tmp_path)
    cfg = Config.from_env()
    assert cfg.bind_host == "0.0.0.0"
    assert cfg.bind_port == 8080
    assert cfg.state_dir == (tmp_path / "state").resolve()
    assert cfg.secrets_dir == (tmp_path / "secrets").resolve()
    assert cfg.base_url == "http://127.0.0.1:8080"
    assert cfg.log_level == "INFO"
    assert cfg.log_file is False


def test_config_env_overrides(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    monkeypatch.setenv("KITCHEN_DISPLAY_STATE_DIR", str(tmp_path / "s"))
    monkeypatch.setenv("KITCHEN_DISPLAY_SECRETS_DIR", str(tmp_path / "k"))
    monkeypatch.setenv("KITCHEN_DISPLAY_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("KITCHEN_DISPLAY_BIND_PORT", "9090")
    monkeypatch.setenv("KITCHEN_DISPLAY_BASE_URL", "http://localhost:9090")
    monkeypatch.setenv("KITCHEN_DISPLAY_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("KITCHEN_DISPLAY_LOG_FILE", "1")
    cfg = Config.from_env()
    assert cfg.state_dir == (tmp_path / "s").resolve()
    assert cfg.secrets_dir == (tmp_path / "k").resolve()
    assert cfg.bind_host == "127.0.0.1"
    assert cfg.bind_port == 9090
    assert cfg.base_url == "http://localhost:9090"
    assert cfg.log_level == "DEBUG"
    assert cfg.log_file is True


def test_config_paths_derived_from_state_dir(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    monkeypatch.setenv("KITCHEN_DISPLAY_STATE_DIR", str(tmp_path / "s"))
    cfg = Config.from_env()
    assert cfg.bmp_path() == (tmp_path / "s").resolve() / "current.bmp.gz"
    assert cfg.etag_path() == (tmp_path / "s").resolve() / "current.etag"
    assert cfg.device_state_path() == (tmp_path / "s").resolve() / "device.json"
    assert cfg.log_file_path() == (tmp_path / "s").resolve() / "server.log"


def test_load_token_strips_whitespace(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "device.token").write_text("  abc123  \n")
    monkeypatch.setenv("KITCHEN_DISPLAY_SECRETS_DIR", str(secrets))
    cfg = Config.from_env()
    assert cfg.load_token() == "abc123"


def test_load_token_missing_raises(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    monkeypatch.setenv("KITCHEN_DISPLAY_SECRETS_DIR", str(tmp_path / "secrets"))
    cfg = Config.from_env()
    with pytest.raises(TokenError, match="not found"):
        cfg.load_token()


def test_load_token_empty_raises(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "device.token").write_text("   \n")
    monkeypatch.setenv("KITCHEN_DISPLAY_SECRETS_DIR", str(secrets))
    cfg = Config.from_env()
    with pytest.raises(TokenError, match="empty"):
        cfg.load_token()
