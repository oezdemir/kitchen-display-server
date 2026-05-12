from __future__ import annotations

import json

import httpx
from helpers import make_bmp
from typer.testing import CliRunner

from xte_kitchen_server.cli import app as cli_app  # noqa: I001


def _make_runner(monkeypatch, test_client):
    """Wire the CLI's httpx.Client to the FastAPI TestClient transport."""

    def factory(base_url: str) -> httpx.Client:
        return httpx.Client(transport=test_client._transport, base_url=base_url)

    monkeypatch.setattr("xte_kitchen_server.cli._make_client", factory)
    return CliRunner()


def test_cli_status_returns_empty_state(monkeypatch, app, client):
    runner = _make_runner(monkeypatch, client)
    monkeypatch.setenv("XTE_KITCHEN_BASE_URL", "http://server")
    result = runner.invoke(cli_app, ["status"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["current"] is None
    assert payload["device"]["recent"] == []


def test_cli_set_image_uploads_and_status_reflects_it(monkeypatch, tmp_path, app, client):
    runner = _make_runner(monkeypatch, client)
    monkeypatch.setenv("XTE_KITCHEN_BASE_URL", "http://server")
    bmp = make_bmp()
    p = tmp_path / "img.bmp"
    p.write_bytes(bmp)
    r1 = runner.invoke(cli_app, ["set-image", str(p)])
    assert r1.exit_code == 0, r1.output
    assert '"etag"' in r1.stdout
    r2 = runner.invoke(cli_app, ["status"])
    assert r2.exit_code == 0, r2.output
    body = json.loads(r2.stdout)
    assert body["current"]["bytes_raw"] == len(bmp)


def test_cli_clear_returns_ok(monkeypatch, tmp_path, app, client):
    runner = _make_runner(monkeypatch, client)
    monkeypatch.setenv("XTE_KITCHEN_BASE_URL", "http://server")
    p = tmp_path / "img.bmp"
    p.write_bytes(make_bmp())
    runner.invoke(cli_app, ["set-image", str(p)])
    r = runner.invoke(cli_app, ["clear"])
    assert r.exit_code == 0, r.output
    assert '"ok": true' in r.stdout.lower()


def test_cli_set_image_nonzero_on_invalid_input(monkeypatch, tmp_path, app, client):
    runner = _make_runner(monkeypatch, client)
    monkeypatch.setenv("XTE_KITCHEN_BASE_URL", "http://server")
    p = tmp_path / "bad.bin"
    p.write_bytes(b"not an image")
    r = runner.invoke(cli_app, ["set-image", str(p)])
    assert r.exit_code != 0
    assert "415" in r.output or "Unsupported" in r.output
