"""Atomic on-disk storage for the current image + telemetry ring."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_MAX_RING = 100


def compute_etag(bmp_bytes: bytes) -> str:
    """ETag format per design §6 and matching the mock host: '"<sha256[:16]>"'."""
    return '"' + hashlib.sha256(bmp_bytes).hexdigest()[:16] + '"'


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_str = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_str)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        # Sweep any stray *.tmp files left by interrupted prior writes.
        for stray in path.parent.glob(path.name + "*.tmp"):
            stray.unlink(missing_ok=True)
    finally:
        if tmp.exists():
            tmp.unlink()


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


def _now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat(timespec="milliseconds")


class Storage:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    # ----- image -----

    def _bmp_path(self) -> Path:
        return self.state_dir / "current.bmp.gz"

    def _etag_path(self) -> Path:
        return self.state_dir / "current.etag"

    def _meta_path(self) -> Path:
        return self.state_dir / "current.meta.json"

    def has_image(self) -> bool:
        return self._bmp_path().exists() and self._etag_path().exists()

    def read_image_gz(self) -> bytes:
        return self._bmp_path().read_bytes()

    def read_etag(self) -> str:
        return self._etag_path().read_text().strip()

    def read_meta(self) -> dict | None:
        if not self._meta_path().exists():
            return None
        return json.loads(self._meta_path().read_text())

    def write_image(self, bmp_bytes: bytes) -> dict:
        gz = gzip.compress(bmp_bytes)
        etag = compute_etag(bmp_bytes)
        meta = {
            "etag": etag,
            "sha256": hashlib.sha256(bmp_bytes).hexdigest(),
            "bytes_raw": len(bmp_bytes),
            "bytes_gz": len(gz),
            "updated_at": _now_iso(),
        }
        _atomic_write_bytes(self._bmp_path(), gz)
        _atomic_write_text(self._etag_path(), etag)
        _atomic_write_text(self._meta_path(), json.dumps(meta))
        return meta

    def clear_image(self) -> None:
        for p in (self._bmp_path(), self._etag_path(), self._meta_path()):
            if p.exists():
                p.unlink()

    # ----- telemetry ring -----

    def _device_path(self) -> Path:
        return self.state_dir / "device.json"

    def read_device_state(self) -> dict:
        if not self._device_path().exists():
            return {
                "last_seen_at": None,
                "last_battery_pct": None,
                "last_user_agent": None,
                "recent": [],
            }
        return json.loads(self._device_path().read_text())

    def record_device_query(self, payload: dict) -> None:
        state = self.read_device_state()
        entry = {"at": _now_iso(), **payload}
        recent = [entry, *state.get("recent", [])][:_MAX_RING]
        new_state = {
            "last_seen_at": entry["at"],
            "last_battery_pct": entry.get("battery_pct", state.get("last_battery_pct")),
            "last_user_agent": entry.get("ua", state.get("last_user_agent")),
            "recent": recent,
        }
        _atomic_write_text(self._device_path(), json.dumps(new_state))
