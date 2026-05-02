#!/usr/bin/env bash
# NemoClaw installer on macOS: curl | bash often runs Bash 3.2, which breaks
# resume prompts using ${_var,,} (requires Bash 4+). Prefer Homebrew Bash, or
# run nemoclaw onboard directly (see messages below).
set -euo pipefail

NBASH=""
for candidate in /opt/homebrew/bin/bash /usr/local/bin/bash; do
  if [[ ! -x "${candidate}" ]]; then
    continue
  fi
  ver="$("${candidate}" -c 'echo "${BASH_VERSINFO[0]}"')"
  if [[ "${ver}" -ge 4 ]]; then
    NBASH=${candidate}
    break
  fi
done

if [[ -z "${NBASH}" ]]; then
  echo "NemoClaw install.sh uses Bash 4+ syntax; macOS /bin/bash is 3.2."
  echo "Install: brew install bash"
  echo "Then:    curl -fsSL https://www.nvidia.com/nemoclaw.sh | /opt/homebrew/bin/bash"
  echo ""
  echo "CLI already installed? Skip curl and run (no resume bug):"
  echo "  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
  echo "  nemoclaw onboard --resume"
  exit 1
fi

curl -fsSL https://www.nvidia.com/nemoclaw.sh | "${NBASH}"
