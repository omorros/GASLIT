#!/usr/bin/env bash
# GASLIT — start the Sentinel (Teammate 1).
#
# Two modes, chosen by the SENTINEL_MODE env var (defaulting to "local"):
#
#   local  — runs `python -m gaslit.agents.sentinel` in the background, writes
#            PID to .sentinel.pid and logs to sentinel.log. Idempotent:
#            re-running exits 0 if an existing process is still healthy.
#
#   ecs    — scales the ECS service (ECS_CLUSTER / ECS_SERVICE) to
#            desiredCount=1 in eu-west-2 via the AWS CLI.
#
# Usage:
#   scripts/start_sentinel.sh
#   SENTINEL_MODE=ecs scripts/start_sentinel.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODE="${SENTINEL_MODE:-local}"

if [ "$MODE" = "ecs" ]; then
    : "${AWS_REGION:=eu-west-2}"
    : "${ECS_CLUSTER:?ECS_CLUSTER env var required}"
    : "${ECS_SERVICE:?ECS_SERVICE env var required}"
    echo "[start_sentinel] scaling ECS service $ECS_SERVICE in $ECS_CLUSTER ($AWS_REGION) to 1"
    aws ecs update-service \
        --cluster "$ECS_CLUSTER" \
        --service "$ECS_SERVICE" \
        --desired-count 1 \
        --region "$AWS_REGION" \
        ${AWS_PROFILE:+--profile "$AWS_PROFILE"} \
        >/dev/null
    echo "[start_sentinel] ECS service scaled to 1; poll /api/sentinel-status for 'online'"
    exit 0
fi

PID_FILE="$REPO_ROOT/.sentinel.pid"
LOG_FILE="$REPO_ROOT/sentinel.log"

if [ -f "$PID_FILE" ]; then
    existing_pid="$(cat "$PID_FILE")"
    if ps -p "$existing_pid" >/dev/null 2>&1; then
        echo "[start_sentinel] already running as PID $existing_pid (log: $LOG_FILE)"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

if [ -d "$REPO_ROOT/.venv" ]; then
    # shellcheck source=/dev/null
    source "$REPO_ROOT/.venv/bin/activate"
fi

# Expat shim — see .env / README. Harmless on systems where these paths don't exist.
export DYLD_LIBRARY_PATH="${DYLD_LIBRARY_PATH:-/opt/homebrew/opt/expat/lib}"
export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/opt/expat/lib}"

nohup python -m gaslit.agents.sentinel >>"$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
echo "[start_sentinel] launched PID $NEW_PID (log: $LOG_FILE)"
