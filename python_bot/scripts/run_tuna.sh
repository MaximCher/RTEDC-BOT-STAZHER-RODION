#!/usr/bin/env bash
set -euo pipefail

# Environment is provided by systemd EnvironmentFile (python_bot/.env).
TUNA_BIN="${TUNA_BIN:-/usr/bin/tuna}"
PORT="${TUNA_HTTP_PORT:-80}"
OUT_FILE="${TUNA_URL_FILE:-/opt/srvt-bot/python_bot/.tuna_url}"

if [ -z "${TUNA_TOKEN:-}" ]; then
  echo "TUNA_TOKEN is empty. Set it in /opt/srvt-bot/python_bot/.env (or via GitHub Secret TUNA_TOKEN) and restart srvt-tuna.service."
  exit 3
fi

# Persist token in tuna config (idempotent). We intentionally do not print the token.
${TUNA_BIN} config save-token "${TUNA_TOKEN}" >/dev/null 2>&1 || true

# Optional: attempt to keep a stable URL across restarts.
# If TUNA_SUBDOMAIN is set and allowed, tuna will try to use it.
SUBDOMAIN_ARGS=()
if [ -n "${TUNA_SUBDOMAIN:-}" ]; then
  SUBDOMAIN_ARGS=(--subdomain="${TUNA_SUBDOMAIN}")
fi

# Start tunnel and persist the current public URL to OUT_FILE when it appears in logs.
# We keep forwarding logs to stdout so systemd/journalctl shows them too.
${TUNA_BIN} http "${PORT}" "${SUBDOMAIN_ARGS[@]}" 2>&1 | while IFS= read -r line; do
  echo "${line}"
  if [[ "${line}" =~ Forwarding\ (https://[^[:space:]]+)\ -> ]]; then
    url="${BASH_REMATCH[1]}"
    ( umask 022 && echo "${url}" > "${OUT_FILE}" ) || true
  fi
done


