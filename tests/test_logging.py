from __future__ import annotations

import logging
import re
from io import StringIO

from xte_kitchen_server.logging_setup import KeyValueFormatter, log_event

ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2}  INFO  "
)


def test_formatter_iso_8601_with_millis_and_offset():
    formatter = KeyValueFormatter()
    record = logging.LogRecord("x", logging.INFO, "f.py", 1, "msg", None, None)
    line = formatter.format(record)
    assert ISO_RE.match(line), f"line did not match ISO-8601 prefix: {line}"


def test_log_event_emits_key_value_fields():
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(KeyValueFormatter())
    logger = logging.getLogger("xte.test1")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    log_event(logger, "INFO", "device_get", status=200, etag_in="-", ms=12)
    line = buf.getvalue().rstrip("\n")
    assert "evt=device_get" in line
    assert "status=200" in line
    assert 'etag_in="-"' in line
    assert "ms=12" in line


def test_log_event_quotes_strings_with_spaces():
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(KeyValueFormatter())
    logger = logging.getLogger("xte.test2")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    log_event(logger, "INFO", "boot", version="0.1.0", note="hello world")
    line = buf.getvalue().rstrip("\n")
    assert 'version="0.1.0"' in line
    assert 'note="hello world"' in line
