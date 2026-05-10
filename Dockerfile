FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PATH=/mcp

WORKDIR /app

COPY pyproject.toml README.md ./
COPY anygpu ./anygpu
COPY mcp_server ./mcp_server

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "MCP_PORT=${PORT:-8000} python -m mcp_server.server"]
