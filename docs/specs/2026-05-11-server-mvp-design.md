# xte-kitchen-server — MVP design

**Date:** 2026-05-11
**Status:** Draft, awaiting user review
**Contract this implements:** `docs/kitchen-host-api.md` in the parent xteink-x4 repo (binding)
**Target host:** `bot@bot0` (LAN), install path `/home/bot/apps/xte-kitchen-server/` (source); `~/.local/...` (installed CLI/daemon)
**Future consumer:** a local "Hermes" agent that renders kitchen-display images and invokes the CLI as one of its skills

This project is also the **first instance of a reusable pattern** for Hermes-driven capabilities (see §16): each capability ships a wheel that pipx installs into one or two console-scripts (CLI ± daemon), an optional systemd unit, and a small SKILL.md bundle the agent picks up. Future capabilities (lights, calendar, …) follow the same shape.

## 1. Scope

A small HTTP service plus a CLI for the Hermes agent. The server has two responsibilities and nothing else:

1. **Serve** the current 800×480 BMP to the Xteink X4 in exactly the wire format the firmware expects (per the binding contract).
2. **Accept** a new image from a local agent through a CLI/HTTP interface, and remember telemetry the device sends back.

Explicitly **not** in scope:
- Image rendering, dithering choices, layout, fonts, content — Hermes' job.
- Upstream data scraping (menus, weather) — Hermes' job.
- The "no lies" §5 rule from the contract — that's the agent's responsibility, since the server only stores what it's told to store.
- Multi-device support, HTTPS, internet exposure, web UI.

The server is **dumb storage in the shape of the device contract.** That's it.

## 2. Wire-format facts (cited from the contract)

- `GET /api/v1/sleep.bmp` is the only endpoint the device knows.
- Auth is **required**: `Authorization: Bearer <token>`. Wrong/missing → `401`. (`docs/kitchen-host-api.md` §6 + §3.3.)
- `If-None-Match: "<etag>"` is sent by the device when it has a prior ETag.
- On match → `304 Not Modified` + same `ETag` header.
- On miss / first request → `200 OK` with:
  - `Content-Type: image/bmp`
  - `Content-Encoding: gzip`
  - `ETag: "<opaque-≤128-char>"`
  - body = gzipped BMP bytes
- BMP must be exactly 800×480, valid `BM` header, bpp ∈ {1,2,4,8,24,32}, no RLE.
- Device captures the `ETag` header literally and replays it. ETag string must round-trip byte-for-byte.

Reference oracle: `code/crosspoint-reader/scripts/mock_kitchen_host.py` in the firmware repo. Our server must respond identically (modulo content) to the same device request.

## 3. Architecture

```
┌─────────────────────── bot0 ──────────────────────────────┐
│                                                           │
│  Hermes agent (future)                                    │
│        │                                                  │
│        │  invokes                                         │
│        ▼                                                  │
│  xte-kitchen CLI ──HTTP→ 127.0.0.1:8080 ──┐               │
│                                            │              │
│                                            ▼              │
│                                ┌──────── FastAPI ────┐    │
│  /api/v1/sleep.bmp  ◄──────────┤ device endpoint     │    │
│  /api/v1/image      ◄──────────┤ agent endpoints     │    │
│  /api/v1/state      ◄──────────┤                     │    │
│                                └─────────┬───────────┘    │
│                                          │                │
│                                          ▼                │
│                                ┌── state/ + secrets/ ──┐  │
│                                │ current.bmp.gz        │  │
│                                │ current.etag          │  │
│                                │ device.json           │  │
│                                │ device.token          │  │
│                                └───────────────────────┘  │
└───────────────────────────────────────────────────────────┘
        │                                  ▲
        └── 0.0.0.0:8080 over LAN ─────────┘
                                Xteink X4
```

Single process. FastAPI app behind uvicorn. systemd manages it. Both the device endpoint and the agent endpoints live on the same port, but agent endpoints reject any source IP that isn't loopback (cheap defense-in-depth: agent endpoints have no token).

## 4. Endpoints

### 4.1 Device-facing

`GET /api/v1/sleep.bmp`

- **Auth:** `Authorization: Bearer <token>` required. 401 on mismatch/missing.
- **Conditional:** if `If-None-Match` header matches current stored ETag → `304` with `ETag` header echoed.
- **200 path:** `Content-Type: image/bmp`, `Content-Encoding: gzip`, `ETag: "<etag>"`, `Content-Length` of gzipped body. Body = bytes from `state/current.bmp.gz`.
- **503 path:** when no image has been uploaded yet. (Spec §3.3: anything ≠ 200/304 is "Failed" from device's perspective and triggers default-image / stale fallback — that's the correct outcome here.)
- **Telemetry capture (best-effort, never fails the request):**
  - `User-Agent` (firmware version string)
  - `X-Battery-Pct` (0–100, per contract §2; informational)
  - `X-Battery-Mv` (raw mV; **speculative future-proofing — not in current firmware**)
  - `X-Charging` (`0|1`; speculative future-proofing)
  - `If-None-Match` value as `etag_sent`
  - Returned status as `status_returned`
  - Request timestamp (ISO 8601, host local TZ)
  - These get appended to `state/device.json` as the latest entry; we keep a bounded ring of the last 100.

### 4.2 Agent-facing (loopback only)

All three require source IP ∈ {`127.0.0.1`, `::1`}. Wrong source → `403`. No bearer token (filesystem trust on the host).

`POST /api/v1/image`
- Body: raw image bytes (`Content-Type` is informational; we sniff magic bytes).
- BMP detection: first two bytes `BM`. Validation: parse with Pillow, assert width=800 & height=480, assert mode/depth supported, no compression. Pass-through; we don't re-encode.
- PNG detection: first eight bytes `\x89PNG\r\n\x1a\n`. Conversion: Pillow → resize/check 800×480 → `convert("1")` with Floyd–Steinberg dithering → save as uncompressed 1-bit BMP.
- Anything else → `415 Unsupported Media Type`.
- On success: gzip the BMP bytes; atomically replace `state/current.bmp.gz` and `state/current.etag`. Respond `200` with JSON `{ etag, sha256, bytes_raw, bytes_gz }`.

`DELETE /api/v1/image`
- Removes `state/current.bmp.gz` and `state/current.etag`. Device endpoint starts returning 503 again. Returns `200 {ok: true}`.

`GET /api/v1/state`
- Returns:
  ```json
  {
    "current": {
      "etag": "\"abc123...\"",
      "sha256": "abc123...",
      "bytes_raw": 48054,
      "bytes_gz": 3120,
      "updated_at": "2026-05-11T08:30:00-07:00"
    },
    "device": {
      "last_seen_at": "2026-05-11T08:35:01-07:00",
      "last_battery_pct": 87,
      "last_user_agent": "CrossPoint-ESP32-1.2.3-kitchen",
      "recent": [ /* up to 100 entries, newest first */ ]
    }
  }
  ```
- Either top-level key may be `null` when there's no data yet.

## 5. CLI

The wheel exposes **two** console-script entry points declared in `pyproject.toml`:

| Entry point | Used by | Purpose |
|---|---|---|
| `xte-kitchen` | Hermes agent (via SKILL.md) and humans | Thin HTTP client to the local daemon |
| `xte-kitchen-server` | systemd | Runs uvicorn against the FastAPI app |

After `pipx install <wheel>` both land in `~/.local/bin/` and are on PATH. No `pixi run` indirection in production.

`xte-kitchen` commands (talk to `${XTE_KITCHEN_BASE_URL}`, default `http://127.0.0.1:${XTE_KITCHEN_BIND_PORT}`):

| Command | Behavior |
|---|---|
| `xte-kitchen set-image <path>` | Read file, POST `/api/v1/image` with raw bytes. Print returned JSON. Non-zero exit on failure. |
| `xte-kitchen clear` | DELETE `/api/v1/image`. |
| `xte-kitchen status` | GET `/api/v1/state`, pretty-print. |

`xte-kitchen-server` commands:

| Command | Behavior |
|---|---|
| `xte-kitchen-server [--host H] [--port P]` | Runs `uvicorn xte_kitchen_server.server:app` with sensible defaults from env vars. Used as `ExecStart` in the systemd unit. |

Environment overrides (consumed by both CLI and server):

| Env var | Default | Purpose |
|---|---|---|
| `XTE_KITCHEN_STATE_DIR` | `./state` (relative to repo root in dev; `/home/bot/apps/xte-kitchen-server/state` in prod) | Where `current.bmp.gz`, `current.etag`, `device.json` live |
| `XTE_KITCHEN_SECRETS_DIR` | `./secrets` / `…/secrets` | Where `device.token` lives |
| `XTE_KITCHEN_BIND_HOST` | `0.0.0.0` | uvicorn host |
| `XTE_KITCHEN_BIND_PORT` | `8080` | uvicorn port (matches firmware default `Config::port = 8080`) |
| `XTE_KITCHEN_BASE_URL` | `http://127.0.0.1:${XTE_KITCHEN_BIND_PORT}` | CLI → server target |

## 6. Storage model

```
/home/bot/apps/xte-kitchen-server/
├── state/                       # gitignored, owned by service user
│   ├── current.bmp.gz           # exact bytes the device receives on 200
│   ├── current.etag             # quoted ETag string, one line
│   └── device.json              # telemetry ring (≤100 entries) + last_seen
├── secrets/                     # gitignored, mode 0700
│   └── device.token             # one line, no quotes, no trailing newline-significance
└── …code, pixi, systemd…
```

- **Atomicity:** every write is `tmp → fsync → rename`. Both `current.bmp.gz` and `current.etag` get re-written under a `flock` so a device request can never read mismatched gz/etag.
- **ETag format:** `'"' + sha256(bmp_bytes).hexdigest()[:16] + '"'` (matches the mock host; 18 chars total, well under the 128-char limit). The truncated hash is deterministic and content-addressed — same content → same ETag → device 304s correctly.
- **Bounded telemetry:** `device.json` keeps at most 100 most-recent entries. Older entries drop off. Keeps the file small and bounded.

## 7. Auth

- Single shared bearer token for the device endpoint, per contract §6.
- Stored in `secrets/device.token`, mode `0600`. One line.
- Generated once by the operator: `openssl rand -hex 32 > secrets/device.token && chmod 600 secrets/device.token`.
- Same token configured on the X4 via its webUI.
- Server reads the token at startup. If the file is missing or empty, the server **refuses to start** with a helpful error pointing at the openssl command.
- Token rotation: replace the file + `systemctl restart xte-kitchen-server` + update the device. No SIGHUP support in MVP (YAGNI).
- Agent endpoints rely on loopback binding for auth — no token, no header dance for the CLI.

## 8. Error handling

| Endpoint | Condition | Status | Body |
|---|---|---|---|
| `GET /api/v1/sleep.bmp` | Bad/missing bearer | 401 | empty |
| `GET /api/v1/sleep.bmp` | ETag match | 304 | empty + `ETag` header |
| `GET /api/v1/sleep.bmp` | No image set | 503 | `text/plain` "no image" |
| `GET /api/v1/sleep.bmp` | Image present | 200 | gzipped BMP |
| `POST /api/v1/image` | Non-loopback source | 403 | `{detail}` |
| `POST /api/v1/image` | Unrecognised magic | 415 | `{detail}` |
| `POST /api/v1/image` | BMP but wrong dims / bpp / compressed | 422 | `{detail}` with reason |
| `POST /api/v1/image` | PNG fails to decode | 422 | `{detail}` |
| any | Internal | 500 | logged |

Telemetry capture never raises into the device path. A failed write to `device.json` is logged and otherwise ignored.

## 9. Logging

Every log line carries a high-resolution timestamp and structured `key=value` fields. The format is deliberately greppable for after-the-fact tracing.

**Format** (single line, ISO 8601 + millis + offset):

```
2026-05-11T08:30:01.234-07:00  INFO  evt=device_get   status=200  etag_in="-"            etag_out="abc123def4567890"  ua="CrossPoint-ESP32-1.2.3-kitchen"  battery_pct=87   ms=12
2026-05-11T08:30:01.234-07:00  INFO  evt=device_get   status=304  etag_in="abc123def..."  etag_out="abc123def..."        ua="CrossPoint-ESP32-1.2.3-kitchen"  battery_pct=86   ms=3
2026-05-11T08:31:00.000-07:00  INFO  evt=image_post   sha256=abc...  bytes_raw=48054  bytes_gz=3120  source_ip=127.0.0.1
2026-05-11T08:32:00.000-07:00  WARN  evt=device_get   status=401  reason=bad_token       source_ip=192.168.1.42
```

Required keys per event:

| Event | Required fields |
|---|---|
| `device_get` | `status`, `etag_in`, `etag_out`, `ua`, `battery_pct` (or `-`), `ms` |
| `image_post` | `sha256`, `bytes_raw`, `bytes_gz`, `source_ip` |
| `image_delete` | `source_ip` |
| `state_get` | `source_ip` |
| `boot` | `version`, `bind`, `state_dir`, `auth=on\|off` (always `on` per §7) |

**Sinks:**
- stdout — primary; journalctl captures it on bot0. (`journalctl -u xte-kitchen-server -f` for live tail; `journalctl -u xte-kitchen-server --since "2 hours ago"` for retrospection.)
- Optional rotating file at `state/server.log` (5 × 5 MB), enabled by `XTE_KITCHEN_LOG_FILE=1`. Off by default to avoid SD/disk churn. Use this if you need offline grep without journalctl.

**Knobs:**
- `XTE_KITCHEN_LOG_LEVEL` (default `INFO`; `DEBUG` for verbose, `WARN` for quiet).
- `XTE_KITCHEN_LOG_FILE` (default `0`).

Telemetry-capture failures (e.g. write to `device.json` fails) log at `WARN` but never propagate into the device request.

## 10. Process model & deployment

- **Dev runtime:** pixi-managed Python 3.12. `pixi.lock` is the source of truth in development. Pixi never runs on the prod box.
- **Prod runtime:** pipx-installed wheel. `pipx install dist/xte_kitchen_server-X.Y.Z-py3-none-any.whl` puts `xte-kitchen` and `xte-kitchen-server` into `~/.local/bin/`. The wheel pins exact dep versions (built from `pixi.lock`), so the install is reproducible without pixi at deploy time.
- **systemd unit (system, not user):** `hermes-xte-kitchen-server.service` (the `hermes-` prefix is a project-wide convention — see §16 — so `systemctl list-units 'hermes-*'` enumerates all agent daemons). Runs as `bot:bot`. Key fields:
  - `ExecStart=/home/bot/.local/bin/xte-kitchen-server`
  - `Environment=XTE_KITCHEN_STATE_DIR=/home/bot/apps/xte-kitchen-server/state`
  - `Environment=XTE_KITCHEN_SECRETS_DIR=/home/bot/apps/xte-kitchen-server/secrets`
  - `Environment=XTE_KITCHEN_BIND_HOST=0.0.0.0`
  - `Environment=XTE_KITCHEN_BIND_PORT=8080`
  - `Restart=on-failure`, `RestartSec=5`
  - `WorkingDirectory=/home/bot/apps/xte-kitchen-server`
- **Files on disk** at deploy time:
  - `~/.local/bin/{xte-kitchen,xte-kitchen-server}` — pipx-installed scripts
  - `~/.local/pipx/venvs/xte-kitchen-server/` — pipx's isolated venv (doesn't pollute system Python)
  - `/home/bot/apps/xte-kitchen-server/{state,secrets}/` — runtime data
  - `/etc/systemd/system/hermes-xte-kitchen-server.service` — unit file
  - `~/.hermes/skills/xte-kitchen/` — skill bundle (see §15)
- **Network:** binds `0.0.0.0:8080`. Don't open a firewall hole if one isn't already in the way — LAN already trusts bot0. (Step 10 of the runbook checks `ufw`/`firewalld` state.) Per contract §7 the API must not be exposed to the internet.

## 11. Tests

| File | Covers |
|---|---|
| `tests/test_image.py` | BMP validation accepts each supported bpp at 800×480, rejects wrong dims, wrong bpp, RLE, non-BMP. PNG conversion produces a valid 1-bit BMP that round-trips through gunzip + Pillow. |
| `tests/test_storage.py` | ETag is deterministic across content. Atomic replace doesn't tear concurrent readers (lock test). `device.json` ring bound holds. |
| `tests/test_server.py` | TestClient: 401 on bad token. 503 with no image. 200 → 304 round-trip with `If-None-Match`. `ETag` header preserved byte-for-byte. `X-Battery-Pct` recorded into state. Loopback enforcement on agent endpoints uses Starlette's `request.client.host`; we don't trust `X-Forwarded-For` since there's no reverse proxy in front of this service. |
| `tests/test_cli.py` | `set-image` returns the etag from a freshly-rendered Pillow BMP. `clear` then GET returns 503. `status` parses JSON. |

`pixi run test` invokes pytest. CI is out of scope for MVP (single-user project).

## 12. Project layout

```
xte-kitchen-server/
├── README.md
├── pixi.toml
├── pixi.lock
├── pyproject.toml        # console-scripts: xte-kitchen, xte-kitchen-server
├── .gitignore
├── docs/specs/2026-05-11-server-mvp-design.md   ← this file
├── src/xte_kitchen_server/
│   ├── __init__.py
│   ├── server.py        # FastAPI app
│   ├── server_entry.py  # xte-kitchen-server console-script (uvicorn launcher)
│   ├── cli.py           # xte-kitchen console-script (Typer)
│   ├── storage.py       # atomic write, etag, telemetry
│   ├── image.py         # BMP validation + PNG→BMP conversion
│   ├── logging_setup.py # ISO 8601 formatter, key=value renderer, rotating-file toggle
│   └── config.py        # env var loading
├── tests/
│   ├── conftest.py
│   ├── test_image.py
│   ├── test_storage.py
│   ├── test_server.py
│   └── test_cli.py
├── systemd/
│   └── hermes-xte-kitchen-server.service
├── skill/               # copied to ~/.hermes/skills/xte-kitchen/ at deploy
│   ├── SKILL.md
│   └── scripts/         # empty in MVP; for future composite wrappers
├── dist/                # gitignored; pixi build-wheel output
│   └── *.whl
├── state/               # gitignored
│   └── .gitkeep
└── secrets/             # gitignored
    └── .gitkeep
```

## 13. Deployment runbook (bot@bot0)

One-time setup, documented for reproducibility. Build happens locally; only the wheel + a few config files travel to bot0.

**On the Mac (build):**

1. `pixi run build-wheel` → produces `dist/xte_kitchen_server-X.Y.Z-py3-none-any.whl` with exact deps pinned from `pixi.lock`.
2. `scp dist/*.whl systemd/hermes-xte-kitchen-server.service skill/SKILL.md bot@bot0:/tmp/deploy/` (or rsync the small files).

**On bot0 (via tmux SSH session — one persistent session for all commands):**

3. Check / install pipx: `command -v pipx || (sudo apt install -y pipx && pipx ensurepath)`. pipx pulls in only Python + the venv tooling that Debian/Ubuntu already package; "minimum system changes" still satisfied.
4. `mkdir -p /home/bot/apps/xte-kitchen-server/{state,secrets} && chmod 700 /home/bot/apps/xte-kitchen-server/secrets`.
5. Generate token: `openssl rand -hex 32 > /home/bot/apps/xte-kitchen-server/secrets/device.token && chmod 600 /home/bot/apps/xte-kitchen-server/secrets/device.token`.
6. Install the wheel: `pipx install /tmp/deploy/xte_kitchen_server-*.whl`. This creates `~/.local/bin/xte-kitchen` and `~/.local/bin/xte-kitchen-server`.
7. Install systemd unit: `sudo cp /tmp/deploy/hermes-xte-kitchen-server.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now hermes-xte-kitchen-server`.
8. ~~Install skill bundle: copy `SKILL.md` to `~/.hermes/skills/xte-kitchen/`.~~ **Deferred** — Hermes is not built yet. `skill/SKILL.md` ships in the repo so the CLI surface is documented in agent-skill format, but the actual drop into `~/.hermes/skills/` happens with the Hermes integration task. Skip this step for now.
9. Smoke test from bot0: `curl -H "Authorization: Bearer $(cat /home/bot/apps/xte-kitchen-server/secrets/device.token)" -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/api/v1/sleep.bmp` — expect `503` (no image set).
10. Smoke test from this Mac: same curl pointed at `http://bot0:8080/…`.
11. Confirm firewall: `ss -tlnp | grep 8080` (must show `0.0.0.0:8080` LISTEN); if `ufw`/`firewalld` is active, allow 8080/tcp from LAN.
12. Inventory check: `systemctl list-units 'hermes-*'` shows `hermes-xte-kitchen-server.service` (and nothing else, today).
13. Push the X4 at it (user step): update kitchen-display host setting on the device to `bot0:8080` and the same bearer token, wait for next wake.

**Upgrades** are: rebuild wheel locally → scp → `pipx install --force /tmp/deploy/xte_kitchen_server-*.whl` → `sudo systemctl restart hermes-xte-kitchen-server`. State and secrets are untouched.

## 14. Build & install (pixi tasks)

Pixi tasks defined in `pixi.toml`:

| Task | What it does |
|---|---|
| `pixi run serve` | Runs `xte-kitchen-server` against `./state` and `./secrets` for local dev. |
| `pixi run cli -- <args>` | Runs `xte-kitchen <args>` against `${XTE_KITCHEN_BASE_URL}`. |
| `pixi run test` | `pytest -q`. |
| `pixi run lint` | `ruff check src/ tests/`. |
| `pixi run build-wheel` | (1) Reads `pixi.lock`, extracts exact PyPI versions, writes them into `pyproject.toml`'s `[project].dependencies` as `==X.Y.Z` pins. (2) `python -m build --wheel` → `dist/*.whl`. The resulting wheel reproduces its dep tree without pixi at install time. |
| `pixi run smoke-install` | Creates a throwaway venv, `pipx`-installs the freshly built wheel into it, runs `xte-kitchen --help` and `xte-kitchen-server --help`. Catches packaging regressions before deploy. |

**No PyInstaller / shiv / makeself tasks.** Wheel + pipx is the only distribution path. If a future target ever lacks Python, we can add a shiv task in ~30 minutes — but YAGNI until then.

## 15. Skill bundle

`skill/SKILL.md` is the agent-facing manifest. It is checked into this repo so it versions in lockstep with the CLI surface. At deploy time it gets copied to `~/.hermes/skills/xte-kitchen/SKILL.md` (along with anything in `skill/scripts/`, currently empty).

Contents follow the Claude-Code skill convention: YAML frontmatter (`name`, `description`, `version`) plus a markdown body that documents every CLI command, its arguments, expected exit codes, and one worked example per command. The body **references the installed CLI by name** (`xte-kitchen set-image …`), not by absolute path, because the CLI is on PATH after pipx install.

`skill/scripts/` is reserved for future composite wrappers (e.g., "fetch upstream → render → upload" as a single shell entry point if the agent ever wants to invoke it atomically). Empty in MVP — the three CLI commands are enough for Hermes to compose its own flow.

When a future capability is added, its `skill/SKILL.md` lives in *its* repo, gets copied to `~/.hermes/skills/<capability-name>/`, and Hermes' skill loader (out of scope here) walks `~/.hermes/skills/*/SKILL.md` to discover everything.

## 16. The reusable pattern (governs all future capabilities)

xte-kitchen-server is the first instance of a deliberate template. Each future Hermes capability follows the same shape so Hermes' integration code stays uniform.

**Rules:**

1. **One capability == one repo == one wheel == (≤1) CLI console-script == (≤1) daemon console-script == (≤1) systemd unit == one `skill/SKILL.md`.** If you need two CLIs or two daemons, you have two capabilities.
2. **Wheel is the canonical artifact.** Self-contained binaries are optional fallbacks, not the default. Wheels pin deps via the `build-wheel` task (see §14).
3. **Pipx is the deploy mechanism. Pixi is the dev mechanism.** Pixi never runs on the prod host. The wheel pins its own deps so `pipx install` is reproducible.
4. **Both the daemon and the CLI are console-scripts in the same wheel**, named `<capability>` (CLI) and `<capability>-server` (daemon, if any). After `pipx install` they sit in `~/.local/bin/`.
5. **systemd units are prefixed `hermes-`** (e.g., `hermes-xte-kitchen-server.service`, `hermes-lights.service`). This lets `systemctl list-units 'hermes-*'` enumerate every agent daemon on the box. The prefix is a hard rule: don't drop it for any capability.
6. **`SKILL.md` references the installed CLI by name**, not by path. `skill/scripts/` is for non-trivial composition only.
7. **Logging convention is shared:** ISO 8601 + millis + offset, key=value fields, journalctl-first. (§9 here is the reference implementation.)
8. **State and secrets live under `/home/bot/apps/<capability>/{state,secrets}`** on bot0, controlled by `<UPPER_CASE_CAPABILITY>_STATE_DIR` / `_SECRETS_DIR` env vars set in the systemd unit.

When a new capability is added, the deploy recipe is identical modulo names: build wheel locally → scp → `pipx install` → drop systemd unit (prefixed) → drop skill bundle → restart.

## 17. Future-proofing notes (documented, **not** implemented)

- **Battery headers:** `X-Battery-Pct` is the only header the contract documents. We also capture `X-Battery-Mv` and `X-Charging` opportunistically so when the firmware adds them, the server already records them with no change. Hermes consumes via `/api/v1/state`.
- **Multi-image / scheduled images:** not in MVP. If we want N images cycled per query, that's an agent concern: agent re-uploads at the desired cadence. Server stays single-image.
- **`/api/v1/dashboard.json` (contract §1):** explicitly out of scope per the contract itself.
- **HTTPS / internet exposure:** explicitly forbidden by contract §7. Don't add.

## 18. Done = ?

MVP is done when:

1. `pixi run test` passes locally.
2. `pixi run build-wheel` produces a wheel with exact dep pins.
3. `pixi run smoke-install` round-trips: the freshly built wheel pipx-installs cleanly into a throwaway venv and `xte-kitchen --help` / `xte-kitchen-server --help` both succeed.
4. The service is up on bot0 under systemd as `hermes-xte-kitchen-server`, restarting on failure. `systemctl list-units 'hermes-*'` shows it.
5. From this Mac: `curl http://bot0:8080/api/v1/sleep.bmp` returns 401 without auth, 503 with auth-but-no-image.
6. Uploading a 800×480 BMP via `xte-kitchen set-image foo.bmp` on bot0 (run as `bot` from any cwd, since pipx put it on PATH) flips the device endpoint to 200 with a valid gzipped BMP body and a stable ETag.
7. A second device request with the previous `If-None-Match` returns 304.
8. `journalctl -u hermes-xte-kitchen-server` shows ISO 8601 timestamped key=value lines for each request, including the captured `X-Battery-Pct` when present.
9. `skill/SKILL.md` exists in the repo and documents every CLI command + exit codes + one worked example per command. (Drop into `~/.hermes/skills/` is **deferred** to the Hermes integration task.)
10. The real X4, pointed at `bot0:8080`, picks up the image on its next wake. (User verifies.)
11. Code, `pixi.lock`, systemd unit, and this spec are committed in a local git repo, ready to push to a private GitHub fork.
