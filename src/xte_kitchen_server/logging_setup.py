"""ISO-8601 + key=value log formatter and setup."""

from __future__ import annotations

import logging
import logging.handlers
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Config


class KeyValueFormatter(logging.Formatter):
    """ISO-8601 + millis + offset, level, then the message verbatim (already key=value)."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=UTC).astimezone()
        return dt.isoformat(timespec="milliseconds")

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record)
        return f"{ts}  {record.levelname:<5}  {record.getMessage()}"


def _render_pairs(**fields: Any) -> str:
    parts = []
    for key, value in fields.items():
        rendered = _render_value(value)
        parts.append(f"{key}={rendered}")
    return "  ".join(parts)


def _render_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    text = str(value)
    if not text.isalnum() or text == "":
        return '"' + text.replace('"', '\\"') + '"'
    return text


def log_event(
    logger: logging.Logger,
    level: str,
    event: str,
    **fields: Any,
) -> None:
    msg = "evt=" + event
    rendered = _render_pairs(**fields)
    if rendered:
        msg = msg + "  " + rendered
    logger.log(getattr(logging, level.upper(), logging.INFO), msg)


def setup_logging(config: Config) -> logging.Logger:
    root = logging.getLogger("xte_kitchen_server")
    root.handlers.clear()
    root.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    stream = logging.StreamHandler()
    stream.setFormatter(KeyValueFormatter())
    root.addHandler(stream)

    if config.log_file:
        Path(config.state_dir).mkdir(parents=True, exist_ok=True)
        rotating = logging.handlers.RotatingFileHandler(
            config.log_file_path(), maxBytes=5 * 1024 * 1024, backupCount=5
        )
        rotating.setFormatter(KeyValueFormatter())
        root.addHandler(rotating)

    return root
