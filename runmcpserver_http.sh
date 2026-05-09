#!/bin/bash
set -euo pipefail

cd /Users/nikhi/nozomio-hackathon

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

export MCP_TRANSPORT="${MCP_TRANSPORT:-streamable-http}"
export MCP_HOST="${MCP_HOST:-0.0.0.0}"
export MCP_PORT="${MCP_PORT:-8000}"
export MCP_PATH="${MCP_PATH:-/mcp}"

exec python -m mcp_server.server
