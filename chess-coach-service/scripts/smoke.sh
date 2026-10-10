#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export COMPOSE_PROJECT_NAME=chess-coach-smoke
export CHESS_COACH_PORT=${CHESS_COACH_SMOKE_PORT:-18081}
BASE="http://127.0.0.1:${CHESS_COACH_PORT}"
cleanup() { docker compose down -v >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker compose down -v --remove-orphans
docker compose build --no-cache
docker compose up -d --wait
curl -fsS "$BASE/" | grep -q 'Chess Coach'
curl -fsS "$BASE/api/health" | grep -q '"ok"'
CHESS_COACH_URL="$BASE" python3 scripts/smoke_api.py seed
docker compose down
docker compose up -d --wait
CHESS_COACH_URL="$BASE" python3 scripts/smoke_api.py verify
echo "SMOKE PASS"
