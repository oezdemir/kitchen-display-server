"""xte-kitchen — thin HTTP client for the local kitchen-display server."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import typer

app = typer.Typer(add_completion=False, help="CLI for xte-kitchen-server.")


def _base_url() -> str:
    return os.environ.get("XTE_KITCHEN_BASE_URL", "http://127.0.0.1:8080")


def _make_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def _print_response(resp: httpx.Response) -> None:
    try:
        typer.echo(json.dumps(resp.json(), indent=2))
    except ValueError:
        typer.echo(resp.text)


def _fail(resp: httpx.Response, op: str) -> None:
    typer.echo(f"{op} failed: HTTP {resp.status_code} — {resp.text}", err=True)
    raise typer.Exit(code=1)


@app.command("set-image")
def set_image(path: Path = typer.Argument(..., exists=True, readable=True)) -> None:  # noqa: B008
    """Upload a BMP or PNG image. The server detects the format and stores it."""
    data = path.read_bytes()
    client = _make_client(_base_url())
    resp = client.post("/api/v1/image", content=data)
    if resp.status_code != 200:
        _fail(resp, "set-image")
    _print_response(resp)


@app.command()
def clear() -> None:
    """Remove the currently-stored image."""
    client = _make_client(_base_url())
    resp = client.delete("/api/v1/image")
    if resp.status_code != 200:
        _fail(resp, "clear")
    _print_response(resp)


@app.command()
def status() -> None:
    """Show current image info and last device telemetry."""
    client = _make_client(_base_url())
    resp = client.get("/api/v1/state")
    if resp.status_code != 200:
        _fail(resp, "status")
    _print_response(resp)


if __name__ == "__main__":
    app()
