#!/usr/bin/env bash
# Run Context Hub CLI from repo root (works even if your shell cwd is elsewhere).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
exec python3 -m context_hub.cli "$@"
