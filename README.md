# xte-kitchen-server

Kitchen-display host service for the Xteink X4 (per the wire contract in
`../docs/kitchen-host-api.md`). Designed to be driven by a future Hermes
agent over a small local CLI.

See `docs/specs/2026-05-11-server-mvp-design.md` for the design, and
`docs/plans/2026-05-11-server-mvp-plan.md` for the build plan.

## Quickstart (dev)

```bash
pixi install
echo "test-token" > secrets/device.token && chmod 600 secrets/device.token
pixi run serve   # listens on 0.0.0.0:8080 by default
# in another shell:
pixi run cli -- status
```

## Build & install

```bash
pixi run build-wheel       # produces dist/xte_kitchen_server-*.whl with exact pins
pixi run smoke-install     # round-trips the wheel through pipx in a throwaway venv
```

## Deploy

See `docs/specs/2026-05-11-server-mvp-design.md` §13.
