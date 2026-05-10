FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY anygpu ./anygpu
COPY mcp_server ./mcp_server

RUN pip install --no-cache-dir .

ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_PATH=/mcp

EXPOSE 8000

CMD ["python", "-m", "mcp_server.server"]
