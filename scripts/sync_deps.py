"""Pin pyproject.toml [project].dependencies from the current env's `pip freeze`.

Run via `pixi run sync-deps` immediately before `python -m build --wheel` so the
resulting wheel has exact dep pins. This bypasses pixi.lock entirely
(pixi.lock is YAML in newer pixi versions; parsing it would require an extra
dep).
"""

from __future__ import annotations

import subprocess
import sys
import tomllib  # py3.12 stdlib
from pathlib import Path

import tomli_w

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

# Runtime deps we want to pin in the wheel.
# Map pip-freeze name (lowercase, no extras) → pyproject spec stem.
RUNTIME: dict[str, str] = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn[standard]",
    "pillow": "pillow",
    "typer": "typer",
    "httpx": "httpx",
    "rich": "rich",
    "starlette": "starlette",
    "pydantic": "pydantic",
}


def _pip_freeze_versions() -> dict[str, str]:
    """Run `pip freeze` and return {lowercase_name: version} for `name==version` lines."""
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
    )
    versions: dict[str, str] = {}
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, _, version = line.partition("==")
        name = name.strip().lower()
        # Strip any extras: e.g. "uvicorn[standard]" → "uvicorn"
        if "[" in name:
            name = name[: name.index("[")]
        versions[name] = version.strip()
    return versions


def main() -> int:
    versions = _pip_freeze_versions()
    pinned = {name: versions[name] for name in RUNTIME if name in versions}
    if not pinned:
        print("error: no runtime versions found via pip freeze", file=sys.stderr)
        return 2

    deps = [f"{RUNTIME[name]}=={pinned[name]}" for name in sorted(pinned)]

    pyproject = tomllib.loads(PYPROJECT.read_text())
    pyproject["project"]["dependencies"] = deps
    PYPROJECT.write_text(tomli_w.dumps(pyproject))

    print(f"Synced {len(deps)} pinned deps into {PYPROJECT}:")
    for d in deps:
        print(f"  {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
