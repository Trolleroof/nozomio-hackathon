#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

exec python -m mcp_server.server
