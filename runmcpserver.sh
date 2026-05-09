#!/bin/bash
set -euo pipefail

cd /Users/nikhi/nozomio-hackathon

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

exec python -m mcp_server.server
