import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from anygpu.gateway import _refresh_deployment_health, make_server
from anygpu.state import initial_state


ROOT = Path(__file__).resolve().parents[1]
FAKE_LLAMA = ROOT / "tests" / "fixtures" / "fake_llama_server.py"


def run_cli(home: Path, *args: str) -> None:
    env = os.environ.copy()
    env["ANYGPU_HOME"] = str(home)
    env["PYTHONPATH"] = str(ROOT)
    env.setdefault("ANYGPU_LLAMA_CPP_SERVER_PATH", sys.executable)
    env.setdefault("ANYGPU_LLAMA_CPP_SERVER_ARGS", str(FAKE_LLAMA))
    env.setdefault("ANYGPU_LLAMA_CPP_CLI_PATH", sys.executable)
    env.setdefault("ANYGPU_LLAMA_CPP_CLI_ARGS", f"{FAKE_LLAMA} --version")
    env.setdefault("ANYGPU_LLAMA_CPP_HEALTH_PATH", "/health")
    env.setdefault("ANYGPU_LOCAL_RUNTIME_PORT_START", "19200")
    env.setdefault("ANYGPU_LOCAL_RUNTIME_PORT_END", "19400")
    result = subprocess.run(
        [sys.executable, "-m", "anygpu", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def prepare_deployment(home: Path) -> None:
    run_cli(home, "login", "--email", "ops@acme.test")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "use", "managed")
    run_cli(home, "compute", "verify", "nvidia-fast")
    run_cli(home, "model", "register", "qwen-prod", "--source", "hf:Qwen/Qwen3-32B", "--task", "chat")
    run_cli(home, "benchmark", "qwen-prod", "--targets", "managed:nvidia-fast", "--duration", "1m")
    run_cli(
        home,
        "policy",
        "create",
        "prod-chat-policy",
        "--objective",
        "balanced",
        "--max-p95",
        "900ms",
        "--fallback",
        "required",
    )
    run_cli(home, "serve", "qwen-prod", "--name", "support-chat-prod", "--policy", "prod-chat-policy")


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode())


def post_json_with_headers(url: str, payload: dict) -> tuple[dict, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        headers = {key.lower(): value for key, value in response.headers.items()}
        return json.loads(response.read().decode()), headers


def post_json_error(url: str, payload: dict) -> tuple[int, dict, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer test"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode()), {
                key.lower(): value for key, value in response.headers.items()
            }
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode()), {key.lower(): value for key, value in error.headers.items()}


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode())


def test_gateway_refreshes_docker_route_health_before_selection(monkeypatch) -> None:
    state = initial_state()
    deployment = {
        "name": "docker-chat",
        "provider": "docker",
        "health": "starting",
        "runtime_process": {"container_name": "anygpu-docker-chat", "health": "starting"},
        "routes": [{"route": "docker:local-docker", "status": "starting"}],
    }

    class FakeDockerProvider:
        def __init__(self, config: dict):
            self.config = config

        def health_check(self, process: dict) -> dict:
            return {"healthy": True, "status": "running"}

    monkeypatch.setattr("anygpu.gateway.DockerProvider", FakeDockerProvider)

    _refresh_deployment_health(state, deployment)

    assert deployment["health"] == "healthy"
    assert deployment["runtime_process"]["health"] == "healthy"
    assert deployment["routes"][0]["status"] == "healthy"


def test_gateway_refreshes_vast_and_vultr_route_health(monkeypatch) -> None:
    state = initial_state()
    vast_deployment = {
        "name": "vast-chat",
        "provider": "vast",
        "health": "provisioning",
        "runtime_process": {"vast_instance_id": "555", "health": "provisioning"},
        "routes": [{"route": "vast:gpu", "status": "provisioning"}],
    }
    vultr_deployment = {
        "name": "vultr-chat",
        "provider": "vultr",
        "health": "provisioning",
        "runtime_process": {"vultr_id": "inst-123", "health": "provisioning"},
        "routes": [{"route": "vultr:gpu", "status": "provisioning"}],
    }

    class FakeVastProvider:
        def __init__(self, config: dict):
            self.config = config

        def health_check(self, process: dict) -> dict:
            return {"healthy": True, "status": "running", "upstream_url": "http://198.51.100.55:18000"}

    class FakeVultrProvider:
        def __init__(self, config: dict):
            self.config = config

        def health_check(self, process: dict) -> dict:
            return {"healthy": True, "status": "active", "upstream_url": "http://203.0.113.10:8000"}

    monkeypatch.setattr("anygpu.gateway.VastProvider", FakeVastProvider)
    monkeypatch.setattr("anygpu.gateway.VultrProvider", FakeVultrProvider)

    _refresh_deployment_health(state, vast_deployment)
    _refresh_deployment_health(state, vultr_deployment)

    assert vast_deployment["health"] == "healthy"
    assert vast_deployment["routes"][0]["runtime_url"] == "http://198.51.100.55:18000"
    assert vast_deployment["upstream_url"] == "http://198.51.100.55:18000/v1/chat/completions"
    assert vultr_deployment["health"] == "healthy"
    assert vultr_deployment["routes"][0]["runtime_url"] == "http://203.0.113.10:8000"
    assert vultr_deployment["upstream_url"] == "http://203.0.113.10:8000/v1/chat/completions"


def test_gateway_lists_models_but_refuses_simulated_chat_routes(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "anygpu"
    prepare_deployment(home)
    monkeypatch.setenv("ANYGPU_HOME", str(home))

    server = make_server("127.0.0.1", 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        time.sleep(0.05)
        health = urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5)
        assert health.status == 200
        models = get_json(f"http://127.0.0.1:{port}/v1/models")
        assert models["object"] == "list"
        assert {model["id"] for model in models["data"]} == {"support-chat-prod"}
        assert models["data"][0]["anygpu"]["simulated"] is True

        status, body, headers = post_json_error(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            {
                "model": "support-chat-prod",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert status == 503
        assert body["error"]["type"] == "runtime_not_available"
        assert "simulated route" in body["error"]["message"]
        assert headers["x-anygpu-simulated"] == "true"
    finally:
        server.shutdown()
        server.server_close()

    with (home / "state.json").open() as handle:
        state = json.load(handle)
    assert not state["usage_events"]
    assert not state["cost_events"]


def test_gateway_refuses_fake_fixture_runtime(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "anygpu"
    monkeypatch.setenv("ANYGPU_HOME", str(home))
    state = initial_state()
    state["deployments"]["fixture-chat"] = {
        "name": "fixture-chat",
        "provider": "local",
        "health": "healthy",
        "runtime_process": {
            "command": [sys.executable, str(FAKE_LLAMA)],
            "health": "healthy",
        },
        "routes": [
            {
                "route": "local:local",
                "pool": "local",
                "runtime": "llama.cpp",
                "status": "healthy",
                "simulated": False,
                "runtime_url": "http://127.0.0.1:19999",
                "upstream_url": "http://127.0.0.1:19999",
                "p95_ms": 1,
            }
        ],
    }
    home.mkdir(parents=True)
    (home / "state.json").write_text(json.dumps(state))

    server = make_server("127.0.0.1", 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        models = get_json(f"http://127.0.0.1:{port}/v1/models")
        assert models["data"][0]["anygpu"]["test_fixture"] is True
        status, body, headers = post_json_error(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            {
                "model": "fixture-chat",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        assert status == 503
        assert body["error"]["type"] == "test_fixture_runtime"
        assert headers["x-anygpu-simulated"] == "false"
    finally:
        server.shutdown()
        server.server_close()


def test_gateway_proxies_real_local_llama_route_with_metadata_headers(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "anygpu"
    monkeypatch.setenv("ANYGPU_HOME", str(home))
    monkeypatch.setenv("ANYGPU_LLAMA_CPP_SERVER_PATH", sys.executable)
    monkeypatch.setenv("ANYGPU_LLAMA_CPP_SERVER_ARGS", str(FAKE_LLAMA))
    monkeypatch.setenv("ANYGPU_LLAMA_CPP_CLI_PATH", sys.executable)
    monkeypatch.setenv("ANYGPU_LLAMA_CPP_CLI_ARGS", f"{FAKE_LLAMA} --version")
    monkeypatch.setenv("ANYGPU_LLAMA_CPP_HEALTH_PATH", "/health")
    monkeypatch.setenv("ANYGPU_ALLOW_TEST_FIXTURE_RUNTIME", "1")
    monkeypatch.setenv("ANYGPU_LOCAL_RUNTIME_PORT_START", "19300")
    monkeypatch.setenv("ANYGPU_LOCAL_RUNTIME_PORT_END", "19500")
    model_path = home / "tiny.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"GGUF-test-model")

    run_cli(home, "login", "--email", "ops@acme.test")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "verify", "local")
    run_cli(home, "model", "register", "tiny-gguf", "--source", str(model_path), "--format", "gguf")
    run_cli(home, "benchmark", "tiny-gguf", "--targets", "local", "--duration", "1m")
    run_cli(home, "policy", "create", "local-policy", "--objective", "fastest", "--max-p95", "2000ms")
    run_cli(home, "serve", "tiny-gguf", "--name", "local-chat", "--policy", "local-policy")

    server = make_server("127.0.0.1", 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body, headers = post_json_with_headers(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            {
                "model": "local-chat",
                "messages": [{"role": "user", "content": "Hello local llama"}],
            },
        )
        assert body["choices"][0]["message"]["content"] == "fake llama response"
        assert headers["x-anygpu-deployment"] == "local-chat"
        assert headers["x-anygpu-route"] == "local"
        assert headers["x-anygpu-runtime"] == "llama.cpp"
        assert headers["x-anygpu-simulated"] == "false"
        assert headers["x-anygpu-upstream"].startswith("http://127.0.0.1:")
    finally:
        server.shutdown()
        server.server_close()
        run_cli(home, "deployments", "stop", "local-chat")
