from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from anygpu.provider import VultrProvider


ROOT = Path(__file__).resolve().parents[1]


def run_cli(home: Path, *args: str, extra_env: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    env["ANYGPU_HOME"] = str(home)
    env["PYTHONPATH"] = str(ROOT)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-m", "anygpu", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def run_cli_raw(home: Path, *args: str, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ANYGPU_HOME"] = str(home)
    env["PYTHONPATH"] = str(ROOT)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "anygpu", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def read_state(home: Path) -> dict:
    with (home / "state.json").open() as handle:
        return json.load(handle)


class VultrFixture:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.deleted: list[str] = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/v2"

    def close(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def _handler(self):
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode() or "{}")
                fixture.requests.append({"method": "POST", "path": self.path, "payload": payload})
                if self.path == "/v2/instances":
                    self._json(
                        {
                            "instance": {
                                "id": "inst-123",
                                "label": payload.get("label"),
                                "region": payload.get("region"),
                                "plan": payload.get("plan"),
                                "main_ip": "203.0.113.10",
                                "status": "pending",
                                "server_status": "installingbooting",
                            }
                        },
                        status=202,
                    )
                    return
                if self.path == "/v2/bare-metals":
                    self._json(
                        {
                            "bare_metal": {
                                "id": "bm-123",
                                "label": payload.get("label"),
                                "region": payload.get("region"),
                                "plan": payload.get("plan"),
                                "main_ip": "203.0.113.20",
                                "status": "pending",
                            }
                        },
                        status=202,
                    )
                    return
                self._json({"error": "unknown path"}, status=404)

            def do_GET(self) -> None:
                fixture.requests.append({"method": "GET", "path": self.path})
                if self.path == "/v2/instances/inst-123":
                    self._json(
                        {
                            "instance": {
                                "id": "inst-123",
                                "main_ip": "203.0.113.10",
                                "status": "active",
                                "server_status": "ok",
                            }
                        }
                    )
                    return
                self._json({"error": "unknown path"}, status=404)

            def do_DELETE(self) -> None:
                fixture.deleted.append(self.path)
                fixture.requests.append({"method": "DELETE", "path": self.path})
                self._json({}, status=204)

            def log_message(self, *_args) -> None:
                return

            def _json(self, payload: dict, status: int = 200) -> None:
                encoded = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                if status != 204:
                    self.wfile.write(encoded)

        return Handler


def test_vultr_provider_creates_cloud_gpu_runtime_with_cloud_init() -> None:
    fixture = VultrFixture()
    try:
        provider = VultrProvider(
            {
                "vultr_api_base_url": fixture.url,
                "vultr_api_key": "test-token",
                "vultr_os_id": 2284,
                "docker_vllm_container_port": 8000,
                "docker_vllm_image": "vllm/vllm-openai:latest",
            }
        )

        handle = provider.create_runtime(
            {
                "name": "qwen-vultr",
                "runtime": "vllm",
                "model_path": "hf:Qwen/Qwen2.5-7B-Instruct",
                "region": "ewr",
                "plan": "vcg-a16-6c-64g-16vram",
                "deployment_kind": "cloud-gpu",
            }
        )

        assert handle["provider"] == "vultr"
        assert handle["resource_type"] == "instance"
        assert handle["vultr_id"] == "inst-123"
        assert handle["upstream_url"] == "http://203.0.113.10:8000"
        request = fixture.requests[0]
        assert request["path"] == "/v2/instances"
        payload = request["payload"]
        assert payload["region"] == "ewr"
        assert payload["plan"] == "vcg-a16-6c-64g-16vram"
        assert payload["os_id"] == 2284
        cloud_init = base64.b64decode(payload["user_data"]).decode()
        assert "docker run" in cloud_init
        assert "vllm/vllm-openai:latest" in cloud_init
        assert "--model Qwen/Qwen2.5-7B-Instruct" in cloud_init
    finally:
        fixture.close()


def test_serve_start_vultr_requires_explicit_cost_confirmation(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    env = {"VULTR_API_KEY": "test-token"}
    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "vultr", "--name", "vultr-prod", extra_env=env)

    result = run_cli_raw(
        home,
        "serve",
        "start",
        "qwen-vultr",
        "--model",
        "hf:Qwen/Qwen2.5-7B-Instruct",
        "--runtime",
        "vllm",
        "--compute",
        "vultr-prod",
        "--plan",
        "vcg-a16-6c-64g-16vram",
        "--region",
        "ewr",
        "--os-id",
        "2284",
        extra_env=env,
    )

    assert result.returncode == 2
    assert "--confirm-cost is required" in result.stderr


def test_serve_start_and_stop_vultr_runtime_records_cloud_metadata(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    fixture = VultrFixture()
    env = {
        "VULTR_API_KEY": "test-token",
        "ANYGPU_VULTR_API_BASE_URL": fixture.url,
    }
    try:
        run_cli(home, "login")
        run_cli(home, "org", "create", "acme-ai")
        run_cli(home, "project", "create", "prod-chat")
        run_cli(home, "compute", "connect", "vultr", "--name", "vultr-prod", extra_env=env)

        started = run_cli(
            home,
            "serve",
            "start",
            "qwen-vultr",
            "--model",
            "hf:Qwen/Qwen2.5-7B-Instruct",
            "--runtime",
            "vllm",
            "--compute",
            "vultr-prod",
            "--plan",
            "vcg-a16-6c-64g-16vram",
            "--region",
            "ewr",
            "--os-id",
            "2284",
            "--confirm-cost",
            extra_env=env,
        )

        assert "Started qwen-vultr on vultr-prod" in started
        assert "http://203.0.113.10:8000/v1/chat/completions" in started
        state = read_state(home)
        deployment = state["deployments"]["qwen-vultr"]
        process = deployment["runtime_process"]
        assert deployment["provider"] == "vultr"
        assert process["vultr_id"] == "inst-123"
        assert process["plan"] == "vcg-a16-6c-64g-16vram"
        assert process["region"] == "ewr"
        assert process["simulated"] is False
        assert deployment["routes"][0]["upstream_url"] == "http://203.0.113.10:8000"

        stopped = run_cli(home, "serve", "stop", "qwen-vultr", extra_env=env)

        assert "Stopped qwen-vultr" in stopped
        assert "/v2/instances/inst-123" in fixture.deleted
        assert read_state(home)["deployments"]["qwen-vultr"]["health"] == "stopped"
    finally:
        fixture.close()
