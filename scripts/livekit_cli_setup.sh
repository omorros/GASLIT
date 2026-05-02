#!/usr/bin/env bash
# LiveKit CLI — align Cloud credentials with this repo (manual copy still required for .env).
#
# Install CLI (pick one):
#   brew install livekit-cli
#   go install github.com/livekit/livekit-cli/v2/lk@latest
#
# Then:
#   lk cloud login
#   lk project list
#
# Copy from the LiveKit Cloud dashboard (same project you use with `lk`):
#   LIVEKIT_URL=wss://YOUR_SUBDOMAIN.livekit.cloud
#   LIVEKIT_API_KEY=APIxxxxxxxx
#   LIVEKIT_API_SECRET=secretxxxxxxxx
#
# Paste into `.env` at the repo root (see `.env.example`). The FastAPI route
# `POST /api/livekit/token` uses these to mint browser JWTs.

set -euo pipefail
if ! command -v lk >/dev/null 2>&1; then
  echo "LiveKit CLI (lk) not found. Install: brew install livekit-cli"
  echo "Docs: https://docs.livekit.io/home/cli/"
  exit 1
fi

echo "LiveKit CLI found: $(lk --version 2>/dev/null || lk version 2>/dev/null || echo ok)"
echo "Run: lk cloud login"
echo "Then open https://cloud.livekit.io and copy URL + API Key + Secret into .env"
