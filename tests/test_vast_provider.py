from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from anygpu.provider import VastProvider


ROOT = Path(__file__).resolve().parents[1]


def run_cli(home: Path, *args: str, extra_env: dict[str, str] | None = None) -> str:
    result = run_cli_raw(home, *args, extra_env=extra_env)
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


class VastFixture:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.deleted: list[str] = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/api/v0"

    def close(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def _handler(self):
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                payload = self._payload()
                fixture.requests.append({"method": "POST", "path": self.path, "payload": payload})
                if self.path == "/api/v0/bundles/":
                    self._json(
                        {
                            "offers": [
                                {
                                    "id": 101,
                                    "gpu_name": "NVIDIA RTX 4090",
                                    "num_gpus": 1,
                                    "gpu_ram": 24576,
                                    "dph_total": 0.42,
                                    "geolocation": "US",
                                    "rentable": True,
                                    "rented": False,
                                    "reliability": 0.998,
                                }
                            ]
                        }
                    )
                    return
                self._json({"error": "unknown path"}, status=404)

            def do_PUT(self) -> None:
                payload = self._payload()
                fixture.requests.append({"method": "PUT", "path": self.path, "payload": payload})
                if self.path == "/api/v0/asks/101/":
                    self._json({"success": True, "new_contract": 555})
                    return
                self._json({"error": "unknown path"}, status=404)

            def do_GET(self) -> None:
                fixture.requests.append({"method": "GET", "path": self.path})
                if self.path == "/api/v0/instances/555/":
                    self._json(
                        {
                            "instances": {
                                "id": 555,
                                "actual_status": "running",
                                "label": "vast-smoke",
                                "public_ipaddr": "198.51.100.55",
                                "ssh_host": "198.51.100.55",
                                "ports": {"8000/tcp": [{"HostIp": "198.51.100.55", "HostPort": "18000"}]},
                            }
                        }
                    )
                    return
                self._json({"error": "unknown path"}, status=404)

            def do_DELETE(self) -> None:
                fixture.deleted.append(self.path)
                fixture.requests.append({"method": "DELETE", "path": self.path})
                self._json({"success": True, "msg": "Instance destroyed successfully"})

            def log_message(self, *_args) -> None:
                return

            def _payload(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                if not length:
                    return {}
                return json.loads(self.rfile.read(length).decode() or "{}")

            def _json(self, payload: dict, status: int = 200) -> None:
                encoded = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler


def test_vast_provider_selects_offer_and_creates_vllm_instance() -> None:
    fixture = VastFixture()
    try:
        provider = VastProvider(
            {
                "vast_api_key": "test-token",
                "vast_api_root_url": fixture.url,
                "docker_vllm_image": "vllm/vllm-openai:latest",
                "docker_vllm_container_port": 8000,
            }
        )

        handle = provider.create_runtime(
            {
                "name": "vast-smoke",
                "runtime": "vllm",
                "model_path": "hf:Qwen/Qwen2.5-0.5B-Instruct",
                "accelerator": "rtx-4090",
                "max_price": 0.5,
            }
        )

        assert handle["provider"] == "vast"
        assert handle["vast_instance_id"] == "555"
        assert handle["offer_id"] == "101"
        assert handle["upstream_url"] == "http://198.51.100.55:18000"
        search = fixture.requests[0]
        assert search["path"] == "/api/v0/bundles/"
        assert search["payload"]["rentable"] == {"eq": True}
        create = fixture.requests[1]
        assert create["path"] == "/api/v0/asks/101/"
        assert create["payload"]["image"] == "vllm/vllm-openai:latest"
        assert create["payload"]["runtype"] == "ssh_direct"
        assert create["payload"]["env"]["MODEL_ID"] == "Qwen/Qwen2.5-0.5B-Instruct"
        assert create["payload"]["env"]["-p 8000:8000"] == "1"
        assert "vllm serve $MODEL_ID" in create["payload"]["onstart"]
    finally:
        fixture.close()


def test_serve_start_vast_requires_cost_confirmation(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    env = {"VAST_AI_API_KEY": "test-token"}
    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "vast", "--name", "vast-prod", extra_env=env)

    result = run_cli_raw(
        home,
        "serve",
        "start",
        "vast-smoke",
        "--model",
        "hf:Qwen/Qwen2.5-0.5B-Instruct",
        "--runtime",
        "vllm",
        "--compute",
        "vast-prod",
        "--accelerator",
        "rtx-4090",
        "--max-price",
        "0.5",
        extra_env=env,
    )

    assert result.returncode == 2
    assert "--confirm-cost is required" in result.stderr


def test_serve_start_and_stop_vast_runtime_records_instance_metadata(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    fixture = VastFixture()
    env = {
        "VAST_AI_API_KEY": "test-token",
        "ANYGPU_VAST_API_ROOT_URL": fixture.url,
    }
    try:
        run_cli(home, "login")
        run_cli(home, "org", "create", "acme-ai")
        run_cli(home, "project", "create", "prod-chat")
        run_cli(home, "compute", "connect", "vast", "--name", "vast-prod", extra_env=env)

        started = run_cli(
            home,
            "serve",
            "start",
            "vast-smoke",
            "--model",
            "hf:Qwen/Qwen2.5-0.5B-Instruct",
            "--runtime",
            "vllm",
            "--compute",
            "vast-prod",
            "--accelerator",
            "rtx-4090",
            "--max-price",
            "0.5",
            "--confirm-cost",
            extra_env=env,
        )

        assert "Started vast-smoke on vast-prod" in started
        assert "base_url: http://127.0.0.1:8765/v1" in started
        assert "model: vast-smoke" in started
        assert "upstream_url: http://198.51.100.55:18000/v1/chat/completions" in started
        deployment = read_state(home)["deployments"]["vast-smoke"]
        process = deployment["runtime_process"]
        assert deployment["provider"] == "vast"
        assert process["vast_instance_id"] == "555"
        assert process["offer_id"] == "101"
        assert process["simulated"] is False

        stopped = run_cli(home, "serve", "stop", "vast-smoke", extra_env=env)

        assert "Stopped vast-smoke" in stopped
        assert "/api/v0/instances/555/" in fixture.deleted
        assert read_state(home)["deployments"]["vast-smoke"]["health"] == "stopped"
    finally:
        fixture.close()
