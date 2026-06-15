# kitchen-display-server

Kitchen-display host service for the Seeed reTerminal E1001. Serves an 800×480 BMP over a
small HTTP wire contract (`GET /api/v1/sleep.bmp`, bearer auth, ETag-based
conditional GET, gzip body) so the device can pull a fresh image on each
deep-sleep wake. Designed to be driven by a future "Hermes" agent over a
local CLI.

**Status:** MVP complete and deployed to `bot@bot0`. 53 unit tests pass; the
service runs under systemd as `hermes-kitchen-display-server`; the CLI is
available as `kitchen-display`.

- Wire contract: `docs/kitchen-host-api.md` (the binding wire contract).
- Design: `docs/specs/2026-05-11-server-mvp-design.md`.
- Build plan: `docs/plans/2026-05-11-server-mvp-plan.md`.

## What's in the wheel

The wheel installs two console-scripts:

| Script | Role |
|---|---|
| `kitchen-display` | Thin HTTP client. The agent (or a human) uses this to push a new image, clear the current image, and inspect device telemetry. |
| `kitchen-display-server` | FastAPI/uvicorn daemon. Started by systemd. Serves the device endpoint on `0.0.0.0:8080` and three loopback-only agent endpoints. |

## CLI

All three commands talk to `${KITCHEN_DISPLAY_BASE_URL}` (default
`http://127.0.0.1:8080`):

```bash
kitchen-display set-image <path>      # upload BMP or PNG (800×480; PNG is dithered to 1-bit BMP)
kitchen-display clear                  # remove current image; device gets 503 until next upload
kitchen-display status                 # current image meta + last device telemetry (battery, UA, etc.)
```

Exit codes: `0` on success; non-zero with stderr message on HTTP error.

## Dev workflow (this Mac)

```bash
pixi install                       # one-time
pixi run test                      # 53 tests, ~0.5 s
pixi run lint                      # ruff check
pixi run fmt                       # ruff format
```

Run the server locally against a throwaway state dir:

```bash
echo "test-token" > secrets/device.token && chmod 600 secrets/device.token
pixi run serve                     # listens on 0.0.0.0:8080
# in another shell:
pixi run cli -- status
```

## Build & smoke-install

```bash
pixi run build-wheel               # syncs pyproject pins from pip freeze, then python -m build
pixi run smoke-install             # pipx-installs the wheel into a throwaway venv and runs --help
```

Output: `dist/kitchen_display_server-0.1.0-py3-none-any.whl`. The wheel's
`[project].dependencies` are pinned to exact versions so `pipx install` is
reproducible without pixi on the target.

## Deploy

Recipe is in `docs/specs/2026-05-11-server-mvp-design.md` §13. Short form:

1. `pixi run build-wheel` on the Mac.
2. `scp` the wheel, the systemd unit, and `skill/SKILL.md` to bot0.
3. On bot0: `pipx install kitchen_display_server-*.whl`.
4. `sudo cp systemd/hermes-kitchen-display-server.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now hermes-kitchen-display-server`.
5. `openssl rand -hex 32 > /home/bot/apps/kitchen-display-server/secrets/device.token` and configure the same token on the device.
6. `systemctl list-units 'hermes-*'` should now show the service. Smoke-test with `curl`.

The `hermes-` prefix on the systemd unit is intentional — every future
agent-driven capability on bot0 follows the same convention so
`systemctl list-units 'hermes-*'` enumerates them all.

## Layout

```
src/kitchen_display_server/
├── config.py            # env → Config dataclass; token loader
├── image.py             # format sniff, BMP validation, PNG → 1-bit BMP
├── storage.py           # atomic file writes, ETag, bounded telemetry ring
├── logging_setup.py     # ISO-8601 + key=value formatter; log_event helper
├── server.py            # FastAPI app factory + 4 routes
├── server_entry.py      # uvicorn launcher (kitchen-display-server console-script)
└── cli.py               # Typer CLI (kitchen-display console-script)

tests/                   # 53 pytest tests
systemd/                 # hermes-kitchen-display-server.service
skill/                   # SKILL.md for the future Hermes agent (not yet deployed)
scripts/                 # sync_deps.py + smoke_install.sh
docs/                    # specs/ + plans/
```

## Operational notes

- **Logs:** `journalctl -u hermes-kitchen-display-server -f` on bot0. ISO-8601
  timestamped, key=value structured.
- **State:** `/home/bot/apps/kitchen-display-server/state/` holds the current
  pre-gzipped BMP, its ETag, and the device-telemetry ring (last 100
  device queries).
- **Secrets:** `/home/bot/apps/kitchen-display-server/secrets/device.token`
  (mode 0600). Same token configured on the device's kitchen-display settings.
- **Sandbox:** the systemd unit runs with `ProtectHome=read-only` and
  `ReadWritePaths=/home/bot/apps/kitchen-display-server` (so atomic writes
  to the state dir work despite the read-only home).

## What's deliberately not here

- **Image rendering / data scraping.** That's the Hermes agent's job; this
  server is dumb storage in the shape of the device contract.
- **The "no lies on stale data" rule** from contract §5 — also the agent's
  job; the server stores whatever it's given.
- **Multi-device support / HTTPS / internet exposure.** Out of scope per
  contract §7 (LAN-only).
- **Hermes integration.** Deferred until the agent exists. `skill/SKILL.md`
  ships in the repo but is not yet copied into `~/.hermes/skills/`.
