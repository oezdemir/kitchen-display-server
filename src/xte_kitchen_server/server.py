"""FastAPI app factory and routes for xte-kitchen-server."""

from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response

from .config import Config
from .image import ImageValidationError, convert_png_to_bmp, detect_format, validate_bmp
from .logging_setup import log_event, setup_logging
from .storage import Storage


def _bearer_dep(config: Config):
    def dep(authorization: str | None = Header(default=None)) -> str:
        expected = config.load_token()
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Unauthorized")
        if authorization[len("Bearer ") :] != expected:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return expected

    return dep


def create_app(config: Config, *, allow_test_loopback: bool = False) -> FastAPI:
    app = FastAPI(title="xte-kitchen-server", version="0.1.0")
    app.state.config = config
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
            storage.record_device_query(
                {
                    "status": 503,
                    "etag_in": if_none_match,
                    "ua": user_agent,
                    "battery_pct": x_battery_pct,
                }
            )
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
            storage.record_device_query(
                {
                    "status": 304,
                    "etag_in": if_none_match,
                    "etag_out": current_etag,
                    "ua": user_agent,
                    "battery_pct": x_battery_pct,
                }
            )
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
        storage.record_device_query(
            {
                "status": 200,
                "etag_in": if_none_match,
                "etag_out": current_etag,
                "ua": user_agent,
                "battery_pct": x_battery_pct,
            }
        )
        return Response(
            status_code=200,
            content=body,
            headers={
                "Content-Type": "image/bmp",
                "Content-Encoding": "gzip",
                "ETag": current_etag,
            },
        )

    def _require_loopback(request: Request) -> None:
        host = request.client.host if request.client else ""
        allowed = {"127.0.0.1", "::1", "localhost"}
        if allow_test_loopback:
            allowed.add("testclient")
        if host not in allowed:
            raise HTTPException(status_code=403, detail=f"loopback only (got {host!r})")

    @app.post("/api/v1/image")
    async def post_image(request: Request):
        _require_loopback(request)
        data = await request.body()
        fmt = detect_format(data)
        try:
            if fmt == "bmp":
                bmp = validate_bmp(data)
            elif fmt == "png":
                bmp = convert_png_to_bmp(data)
            else:
                raise HTTPException(status_code=415, detail="payload must be BMP or PNG")
        except ImageValidationError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        meta = storage.write_image(bmp)
        log_event(
            logger,
            "INFO",
            "image_post",
            sha256=meta["sha256"],
            bytes_raw=meta["bytes_raw"],
            bytes_gz=meta["bytes_gz"],
            source_ip=request.client.host if request.client else "-",
        )
        return meta

    @app.delete("/api/v1/image")
    def delete_image(request: Request):
        _require_loopback(request)
        storage.clear_image()
        log_event(
            logger,
            "INFO",
            "image_delete",
            source_ip=request.client.host if request.client else "-",
        )
        return {"ok": True}

    @app.get("/api/v1/state")
    def get_state(request: Request):
        _require_loopback(request)
        log_event(
            logger,
            "INFO",
            "state_get",
            source_ip=request.client.host if request.client else "-",
        )
        meta = storage.read_meta()
        return {
            "current": meta,
            "device": storage.read_device_state(),
        }

    return app
