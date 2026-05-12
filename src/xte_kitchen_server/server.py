"""FastAPI app factory and routes for xte-kitchen-server."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response

from .config import Config
from .logging_setup import log_event, setup_logging
from .storage import Storage


def _bearer_dep(config: Config):
    def dep(authorization: str | None = Header(default=None)) -> str:
        expected = config.load_token()
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401)
        if authorization[len("Bearer "):] != expected:
            raise HTTPException(status_code=401)
        return expected
    return dep


def create_app(config: Config, *, allow_test_loopback: bool = False) -> FastAPI:
    app = FastAPI(title="xte-kitchen-server", version="0.1.0")
    app.state.config = config
    app.state.allow_test_loopback = allow_test_loopback
    storage = Storage(config.state_dir)
    logger = setup_logging(config)
    bearer = _bearer_dep(config)

    log_event(
        logger,
        "INFO",
        "boot",
        version="0.1.0",
        bind=f"{config.bind_host}:{config.bind_port}",
        state_dir=str(config.state_dir),
        auth="on",
    )

    @app.get("/api/v1/sleep.bmp")
    def sleep_bmp(
        request: Request,
        _: str = Depends(bearer),
        if_none_match: str | None = Header(default=None, alias="If-None-Match"),
        x_battery_pct: int | None = Header(default=None, alias="X-Battery-Pct"),
        user_agent: str | None = Header(default=None, alias="User-Agent"),
    ):
        if not storage.has_image():
            log_event(
                logger,
                "INFO",
                "device_get",
                status=503,
                etag_in=if_none_match,
                ua=user_agent,
                battery_pct=x_battery_pct,
            )
            storage.record_device_query({
                "status": 503, "etag_in": if_none_match,
                "ua": user_agent, "battery_pct": x_battery_pct,
            })
            return Response(status_code=503, content=b"no image", media_type="text/plain")

        current_etag = storage.read_etag()
        if if_none_match == current_etag:
            log_event(
                logger,
                "INFO",
                "device_get",
                status=304,
                etag_in=if_none_match,
                etag_out=current_etag,
                ua=user_agent,
                battery_pct=x_battery_pct,
            )
            storage.record_device_query({
                "status": 304, "etag_in": if_none_match, "etag_out": current_etag,
                "ua": user_agent, "battery_pct": x_battery_pct,
            })
            return Response(status_code=304, headers={"ETag": current_etag})

        body = storage.read_image_gz()
        log_event(
            logger,
            "INFO",
            "device_get",
            status=200,
            etag_in=if_none_match,
            etag_out=current_etag,
            ua=user_agent,
            battery_pct=x_battery_pct,
            bytes_gz=len(body),
        )
        storage.record_device_query({
            "status": 200, "etag_in": if_none_match, "etag_out": current_etag,
            "ua": user_agent, "battery_pct": x_battery_pct,
        })
        return Response(
            status_code=200,
            content=body,
            headers={
                "Content-Type": "image/bmp",
                "Content-Encoding": "gzip",
                "ETag": current_etag,
                "Content-Length": str(len(body)),
            },
        )

    return app
