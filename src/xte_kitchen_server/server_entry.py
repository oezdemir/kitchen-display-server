"""Console-script entry for `xte-kitchen-server`. Boots uvicorn against create_app()."""

from __future__ import annotations

import argparse
import sys

import uvicorn

from .config import Config
from .server import create_app


def main(argv: list[str] | None = None) -> int:
    cfg = Config.from_env()
    parser = argparse.ArgumentParser(
        prog="xte-kitchen-server",
        description="Kitchen-display HTTP host service (FastAPI + uvicorn).",
    )
    parser.add_argument("--host", default=cfg.bind_host, help="bind host (default from env)")
    parser.add_argument(
        "--port", type=int, default=cfg.bind_port, help="bind port (default from env)"
    )
    args = parser.parse_args(argv)

    app = create_app(cfg)
    uvicorn.run(app, host=args.host, port=args.port, log_level=cfg.log_level.lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
