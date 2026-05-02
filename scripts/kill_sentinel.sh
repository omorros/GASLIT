#!/usr/bin/env bash
# GASLIT — kill the Sentinel (Teammate 1).
#
# Two modes, chosen by the SENTINEL_MODE env var (defaulting to "local"):
#
#   local  — SIGTERM the PID in .sentinel.pid (or any stray
#            `gaslit.agents.sentinel` process). Waits briefly, then SIGKILLs.
#
#   ecs    — scales the ECS service to desiredCount=0 via the AWS CLI.
#
# Usage:
#   scripts/kill_sentinel.sh
#   SENTINEL_MODE=ecs scripts/kill_sentinel.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODE="${SENTINEL_MODE:-local}"

if [ "$MODE" = "ecs" ]; then
    : "${AWS_REGION:=eu-west-2}"
    : "${ECS_CLUSTER:?ECS_CLUSTER env var required}"
    : "${ECS_SERVICE:?ECS_SERVICE env var required}"
    echo "[kill_sentinel] scaling ECS service $ECS_SERVICE in $ECS_CLUSTER ($AWS_REGION) to 0"
    aws ecs update-service \
        --cluster "$ECS_CLUSTER" \
        --service "$ECS_SERVICE" \
        --desired-count 0 \
        --region "$AWS_REGION" \
        ${AWS_PROFILE:+--profile "$AWS_PROFILE"} \
        >/dev/null
    echo "[kill_sentinel] ECS service scaled to 0"
    exit 0
fi

PID_FILE="$REPO_ROOT/.sentinel.pid"

kill_with_timeout () {
    local pid="$1"
    kill "$pid" 2>/dev/null || return 0
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        if ! ps -p "$pid" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.3
    done
    kill -9 "$pid" 2>/dev/null || true
}

killed_any=0

if [ -f "$PID_FILE" ]; then
    existing_pid="$(cat "$PID_FILE")"
    if [ -n "$existing_pid" ] && ps -p "$existing_pid" >/dev/null 2>&1; then
        echo "[kill_sentinel] stopping PID $existing_pid"
        kill_with_timeout "$existing_pid"
        killed_any=1
    fi
    rm -f "$PID_FILE"
fi

# Also sweep up any stray processes (e.g. launched outside this script).
stray_pids=$(pgrep -f "gaslit\.agents\.sentinel" || true)
for pid in $stray_pids; do
    if [ -n "$pid" ]; then
        echo "[kill_sentinel] stopping stray PID $pid"
        kill_with_timeout "$pid"
        killed_any=1
    fi
done

if [ "$killed_any" = "0" ]; then
    echo "[kill_sentinel] no sentinel process running"
fi
