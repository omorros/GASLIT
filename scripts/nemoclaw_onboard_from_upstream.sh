#!/usr/bin/env bash
# Onboard NemoClaw using Dockerfile + nemoclaw/ sources from GitHub main.
#
# Fixes sandbox builds that fail at `npm ci` with missing @emnapi/* — the CLI's
# embedded snapshot can lag behind main's package-lock.json.
set -euo pipefail

export PATH="${HOME}/.local/bin:${PATH}"

ROOT="${NEMOCLAW_SRC:-${HOME}/NemoClaw-upstream}"

if ! command -v nemoclaw >/dev/null 2>&1; then
  echo "nemoclaw not on PATH. Install first, then:"
  echo "  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
  exit 1
fi

if [[ ! -f "${ROOT}/Dockerfile" ]]; then
  echo "Cloning NVIDIA/NemoClaw → ${ROOT}"
  git clone --depth 1 https://github.com/NVIDIA/NemoClaw.git "${ROOT}"
else
  echo "Updating ${ROOT}"
  git -C "${ROOT}" pull --ff-only
fi

echo ""
echo "Starting onboard with build context from repo root (parent of Dockerfile)."
echo "If Docker keeps using stale layers:"
echo "  docker builder prune -f"
echo ""

exec nemoclaw onboard --fresh --from "${ROOT}/Dockerfile" "$@"
