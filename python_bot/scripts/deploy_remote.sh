#!/usr/bin/env bash
set -euo pipefail

# Runs on the VPS inside the project directory: ${DEPLOY_PATH}/python_bot
# Requires:
# - docker + docker compose plugin installed
# - .env file exists in the current directory
#
# Optional:
# - WIPE=1 to remove containers + volumes (DB) before deploying

COMPOSE_FILE="docker-compose.prod.yml"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is not available"
  exit 1
fi

if [ ! -f "${COMPOSE_FILE}" ]; then
  echo "ERROR: ${COMPOSE_FILE} not found in $(pwd)"
  exit 1
fi

WIPE="${WIPE:-0}"

echo "Deploying with ${COMPOSE_FILE} (WIPE=${WIPE})"

if [ "${WIPE}" = "1" ]; then
  echo "WIPE=1: stopping and removing containers + volumes..."
  docker compose -f "${COMPOSE_FILE}" down -v --remove-orphans || true
fi

# Build + restart services
docker compose -f "${COMPOSE_FILE}" up -d --build --remove-orphans

# Cleanup: prevent disk from filling with old images.
# 1) Always prune dangling images (old image IDs left after a rebuild) — safe.
echo "Pruning dangling images..."
docker image prune -f >/dev/null 2>&1 || true

# 2) Prune build cache (safe).
echo "Pruning build cache..."
docker builder prune -f >/dev/null 2>&1 || true

# 3) Optionally prune *unused* images older than PRUNE_HOURS (more aggressive).
PRUNE_HOURS="${PRUNE_HOURS:-168}" # 7 days
echo "Pruning unused images older than ${PRUNE_HOURS}h..."
docker image prune -a -f --filter "until=${PRUNE_HOURS}h" >/dev/null 2>&1 || true

echo "OK: deploy finished"
echo "Health: http://<your-host>/health"


