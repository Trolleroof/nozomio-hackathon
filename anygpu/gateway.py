from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
import urllib.error
import urllib.request

from .config import load_config
from .domain import record_usage
from .provider import DockerProvider, VastProvider, VultrProvider
from .state import edit_state, load_state


def _json_response(
    handler: BaseHTTPRequestHandler,
    status: int,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> None:
    encoded = json.dumps(body).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        handler.send_header(key, value)
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _count_tokens(text: str) -> int:
    return max(1, len(text.split()))


def _chat_text(payload: dict[str, Any]) -> str:
    if "messages" in payload:
        return " ".join(str(message.get("content", "")) for message in payload["messages"])
    return str(payload.get("prompt", ""))


def _route_headers(deployment_name: str, route: dict[str, Any]) -> dict[str, str]:
    route_name = "local" if route.get("pool") == "local" else route["route"]
    return {
        "x-anygpu-deployment": deployment_name,
        "x-anygpu-route": route_name,
        "x-anygpu-runtime": route["runtime"],
        "x-anygpu-simulated": str(bool(route.get("simulated", True))).lower(),
        "x-anygpu-upstream": route.get("upstream_url") or route.get("runtime_url") or "",
    }


def _is_test_fixture_runtime(deployment: dict[str, Any]) -> bool:
    if os.environ.get("ANYGPU_ALLOW_TEST_FIXTURE_RUNTIME"):
        return False
    process = deployment.get("runtime_process", {})
    command = process.get("command", [])
    if isinstance(command, str):
        command_text = command
    else:
        command_text = " ".join(str(part) for part in command)
    return "tests/fixtures/fake_llama_server.py" in command_text


def _proxy_to_runtime(
    runtime_url: str,
    path: str,
    payload: dict[str, Any],
    upstream_api_key: str | None = None,
    retry_seconds: float = 30.0,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AnyGPU-Gateway/0.1",
    }
    if upstream_api_key:
        headers["Authorization"] = f"Bearer {upstream_api_key}"
    request = urllib.request.Request(
        f"{runtime_url}{path}",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    deadline = time.time() + retry_seconds
    while True:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode())
                skipped = {"content-length", "content-type", "server", "date", "connection", "transfer-encoding"}
                headers = {key: value for key, value in response.headers.items() if key.lower() not in skipped}
                return response.status, body, headers
        except urllib.error.HTTPError as exc:
            if exc.code == 503 and time.time() < deadline:
                time.sleep(0.5)
                continue
            try:
                body = json.loads(exc.read().decode())
            except json.JSONDecodeError:
                body = {"error": str(exc)}
            return exc.code, body, {}
        except urllib.error.URLError as exc:
            if time.time() < deadline:
                time.sleep(0.5)
                continue
            return 502, {"error": f"runtime_unavailable: {exc.reason}"}, {}


def _refresh_deployment_health(state: dict[str, Any], deployment: dict[str, Any]) -> None:
    provider_name = deployment.get("provider")
    if provider_name not in {"docker", "vast", "vultr"}:
        return
    process = deployment.get("runtime_process")
    if not process or deployment.get("health") == "stopped":
        return
    config = load_config(state.get("config", {}))
    if provider_name == "vast":
        provider = VastProvider(config)
    elif provider_name == "vultr":
        provider = VultrProvider(config)
    else:
        provider = DockerProvider(config)
    health = provider.health_check(process)
    process["health"] = "healthy" if health.get("healthy") else health.get("status", "unknown")
    if health.get("upstream_url"):
        process["upstream_url"] = health["upstream_url"]
        deployment["upstream_url"] = f"{health['upstream_url']}/v1/chat/completions"
    deployment["health"] = process["health"]
    for route in deployment.get("routes", []):
        route["status"] = process["health"]
        if process.get("upstream_url"):
            route["upstream_url"] = process["upstream_url"]
            route["runtime_url"] = process["upstream_url"]


def _model_list(state: dict[str, Any]) -> dict[str, Any]:
    data = []
    for deployment in state.get("deployments", {}).values():
        if deployment.get("health") == "stopped":
            continue
        route = next(iter(deployment.get("routes", [])), {})
        data.append(
            {
                "id": deployment["name"],
                "object": "model",
                "created": int(time.time()),
                "owned_by": "anygpu",
                "anygpu": {
                    "health": deployment.get("health", "unknown"),
                    "provider": deployment.get("provider") or route.get("pool"),
                    "runtime": deployment.get("runtime") or route.get("runtime"),
                    "route": route.get("route"),
                    "simulated": bool(route.get("simulated", True)),
                    "test_fixture": _is_test_fixture_runtime(deployment),
                    "upstream_url": route.get("runtime_url") or route.get("upstream_url"),
                },
            }
        )
    return {"object": "list", "data": sorted(data, key=lambda item: item["id"])}


class AnyGPUGatewayHandler(BaseHTTPRequestHandler):
    server_version = "AnyGPULocalGateway/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/healthz":
            state = load_state()
            deployments = [
                name for name, deployment in state["deployments"].items() if deployment.get("health") == "healthy"
            ]
            _json_response(self, 200, {"status": "ok", "deployments": deployments})
            return
        if self.path == "/v1/models":
            state = load_state()
            _json_response(self, 200, _model_list(state))
            return
        _json_response(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path not in {"/v1/chat/completions", "/v1/completions"}:
            _json_response(self, 404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode() or "{}")
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "invalid_json"})
            return
        deployment_name = str(payload.get("model", ""))
        start = time.perf_counter()
        with edit_state() as state:
            deployment = state["deployments"].get(deployment_name)
            if not deployment:
                _json_response(self, 404, {"error": f"unknown deployment {deployment_name}"})
                return
            _refresh_deployment_health(state, deployment)
            healthy_routes = [route for route in deployment["routes"] if route["status"] == "healthy"]
            if not healthy_routes:
                _json_response(self, 503, {"error": f"deployment {deployment_name} has no healthy routes"})
                return
            route = healthy_routes[0]
            metadata_headers = _route_headers(deployment_name, route)
            if _is_test_fixture_runtime(deployment):
                _json_response(
                    self,
                    503,
                    {
                        "error": {
                            "type": "test_fixture_runtime",
                            "message": (
                                f"Deployment {deployment_name} is backed by the fake llama.cpp test fixture, "
                                "not a real model runtime. Configure llama_cpp_server_path to a real llama-server "
                                "binary or deploy through Docker, Vast, or Vultr."
                            ),
                        }
                    },
                    metadata_headers,
                )
                return
            if not route.get("simulated", True) and route.get("runtime_url"):
                upstream_api_key = (
                    route.get("upstream_api_key")
                    or deployment.get("runtime_process", {}).get("api_key")
                    or deployment.get("upstream_api_key")
                )
                status, body, upstream_headers = _proxy_to_runtime(
                    route["runtime_url"],
                    self.path,
                    payload,
                    upstream_api_key=upstream_api_key,
                )
                usage = body.get("usage", {})
                prompt_tokens = int(usage.get("prompt_tokens", _count_tokens(_chat_text(payload))))
                completion_tokens = int(usage.get("completion_tokens", 1))
                latency_ms = max(1, int((time.perf_counter() - start) * 1000))
                record_usage(state, deployment_name, prompt_tokens, completion_tokens, latency_ms)
                headers = {**upstream_headers, **metadata_headers}
                _json_response(self, status, body, headers)
                return
            reason = "simulated route" if route.get("simulated", True) else "missing runtime_url"
            _json_response(
                self,
                503,
                {
                    "error": {
                        "type": "runtime_not_available",
                        "message": (
                            f"Deployment {deployment_name} is not backed by a real runtime "
                            f"({reason}). Start a real Docker, Vast, Vultr, or local llama.cpp/vLLM runtime."
                        ),
                    }
                },
                metadata_headers,
            )
            return

    def _stream_response(self, body: dict[str, Any], headers: dict[str, str]) -> None:
        content = body["choices"][0]["message"]["content"]
        chunks = [
            {
                "id": body["id"],
                "object": "chat.completion.chunk",
                "created": body["created"],
                "model": body["model"],
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            },
            {
                "id": body["id"],
                "object": "chat.completion.chunk",
                "created": body["created"],
                "model": body["model"],
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            },
        ]
        encoded = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        data = encoded.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), AnyGPUGatewayHandler)


def serve(host: str, port: int) -> None:
    server = make_server(host, port)
    print(f"AnyGPU gateway listening on http://{host}:{port}")
    print(f"OpenAI-compatible endpoint: http://{host}:{port}/v1/chat/completions")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
