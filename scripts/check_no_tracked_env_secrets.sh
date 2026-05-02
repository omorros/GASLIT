#!/usr/bin/env bash
# Fail if any real env file (other than .env.example) is tracked by git.
set -euo pipefail
cd "$(dirname "$0")/.."
bad="$(git ls-files | grep -E '(^|/)\.env($|\.)' | grep -v '\.env\.example$' || true)"
if [[ -n "${bad}" ]]; then
  echo "ERROR: Secret env files must not be committed. Tracked files:" >&2
  echo "${bad}" >&2
  echo "Run: git rm --cached <file>  then add to .gitignore if needed." >&2
  exit 1
fi
echo "OK: no tracked .env files except allowed templates."
