#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v brew >/dev/null; then
  echo "Homebrew is required; see docs/environment.md" >&2
  exit 1
fi
export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_INSTALL_CLEANUP=1
missing=()
command -v ngspice >/dev/null || missing+=(ngspice)
command -v iverilog >/dev/null || missing+=(icarus-verilog)
command -v uv >/dev/null || missing+=(uv)
if ((${#missing[@]})); then
  brew install "${missing[@]}"
fi
make setup
make test
