#!/usr/bin/env bash
set -euo pipefail

# Environment is provided by systemd EnvironmentFile (python_bot/.env).
TUNA_BIN="${TUNA_BIN:-/usr/bin/tuna}"
PORT="${TUNA_HTTP_PORT:-80}"

if [ -z "${TUNA_TOKEN:-}" ]; then
  echo "TUNA_TOKEN is empty. Set it in /opt/srvt-bot/python_bot/.env (or via GitHub Secret TUNA_TOKEN) and restart srvt-tuna.service."
  exit 3
fi

# Persist token in tuna config (idempotent). We intentionally do not print the token.
${TUNA_BIN} config save-token "${TUNA_TOKEN}" >/dev/null 2>&1 || true

exec ${TUNA_BIN} http "${PORT}"


