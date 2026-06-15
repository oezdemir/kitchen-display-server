#!/usr/bin/env bash
# Round-trip the freshly built wheel through pipx in a throwaway venv.
# Catches packaging regressions before deploy.
set -euo pipefail

WHEEL="$(ls -t dist/kitchen_display_server-*.whl 2>/dev/null | head -n1 || true)"
if [[ -z "${WHEEL}" ]]; then
  echo "no wheel in dist/ — run \`pixi run build-wheel\` first" >&2
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

echo "smoke: creating throwaway venv at ${TMP}/venv"
python -m venv "${TMP}/venv"
"${TMP}/venv/bin/pip" install --quiet pipx
PIPX_HOME="${TMP}/pipx-home" PIPX_BIN_DIR="${TMP}/pipx-bin" \
  "${TMP}/venv/bin/pipx" install "${WHEEL}"

echo "smoke: invoking kitchen-display-server --help"
"${TMP}/pipx-bin/kitchen-display-server" --help

echo "smoke: invoking kitchen-display --help"
"${TMP}/pipx-bin/kitchen-display" --help

echo "smoke: ok"
