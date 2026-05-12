"""FastAPI app factory for the xte-kitchen-server."""

from __future__ import annotations

from fastapi import FastAPI

from .config import Config


def create_app(config: Config, *, allow_test_loopback: bool = False) -> FastAPI:
    app = FastAPI(title="xte-kitchen-server", version="0.1.0")
    app.state.config = config
    app.state.allow_test_loopback = allow_test_loopback
    return app
