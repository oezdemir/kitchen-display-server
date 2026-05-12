"""Environment → Config dataclass and token loading."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class TokenError(RuntimeError):
    """Raised when secrets/device.token is missing or empty."""


def _env_path(key: str, default: str) -> Path:
    return Path(os.environ.get(key, default)).resolve()


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, str(default)))


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    state_dir: Path
    secrets_dir: Path
    bind_host: str
    bind_port: int
    base_url: str
    log_level: str
    log_file: bool

    @classmethod
    def from_env(cls) -> Config:
        bind_port = _env_int("XTE_KITCHEN_BIND_PORT", 8080)
        return cls(
            state_dir=_env_path("XTE_KITCHEN_STATE_DIR", "./state"),
            secrets_dir=_env_path("XTE_KITCHEN_SECRETS_DIR", "./secrets"),
            bind_host=os.environ.get("XTE_KITCHEN_BIND_HOST", "0.0.0.0"),
            bind_port=bind_port,
            base_url=os.environ.get(
                "XTE_KITCHEN_BASE_URL", f"http://127.0.0.1:{bind_port}"
            ),
            log_level=os.environ.get("XTE_KITCHEN_LOG_LEVEL", "INFO"),
            log_file=_env_bool("XTE_KITCHEN_LOG_FILE", False),
        )

    def token_path(self) -> Path:
        return self.secrets_dir / "device.token"

    def bmp_path(self) -> Path:
        return self.state_dir / "current.bmp.gz"

    def etag_path(self) -> Path:
        return self.state_dir / "current.etag"

    def device_state_path(self) -> Path:
        return self.state_dir / "device.json"

    def log_file_path(self) -> Path:
        return self.state_dir / "server.log"

    def load_token(self) -> str:
        path = self.token_path()
        if not path.exists():
            raise TokenError(
                f"Device token not found at {path}. "
                "Generate one with: openssl rand -hex 32 > "
                f"{path} && chmod 600 {path}"
            )
        token = path.read_text().strip()
        if not token:
            raise TokenError(f"Device token at {path} is empty.")
        return token
