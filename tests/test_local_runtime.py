import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from anygpu.config import load_config
from anygpu.provider import LocalProvider
from anygpu.runtime import LlamaCppRuntime


ROOT = Path(__file__).resolve().parents[1]
FAKE_LLAMA = ROOT / "tests" / "fixtures" / "fake_llama_server.py"


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


def read_state(home: Path) -> dict:
    with (home / "state.json").open() as handle:
        return json.load(handle)


def local_env(home: Path) -> dict[str, str]:
    return {
        "ANYGPU_LLAMA_CPP_SERVER_PATH": sys.executable,
        "ANYGPU_LLAMA_CPP_SERVER_ARGS": str(FAKE_LLAMA),
        "ANYGPU_LLAMA_CPP_CLI_PATH": sys.executable,
        "ANYGPU_LLAMA_CPP_CLI_ARGS": f"{FAKE_LLAMA} --version",
        "ANYGPU_LLAMA_CPP_HEALTH_PATH": "/health",
        "ANYGPU_MODEL_CACHE_PATH": str(home / "models"),
        "ANYGPU_LOCAL_RUNTIME_HOST": "127.0.0.1",
        "ANYGPU_LOCAL_RUNTIME_PORT_START": "19000",
        "ANYGPU_LOCAL_RUNTIME_PORT_END": "19200",
    }


def test_config_and_runtime_detection_from_environment(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "anygpu"
    monkeypatch.setenv("ANYGPU_HOME", str(home))
    for key, value in local_env(home).items():
        monkeypatch.setenv(key, value)

    config = load_config({})
    assert config["llama_cpp_server_path"] == sys.executable
    assert config["model_cache_path"] == str(home / "models")
    assert config["llama_cpp_health_path"] == "/health"
    assert config["local_runtime_host"] == "127.0.0.1"
    assert config["local_runtime_port_start"] == 19000
    assert config["local_runtime_port_end"] == 19200

    runtime = LlamaCppRuntime(config)
    availability = runtime.detect()
    assert availability["available"] is True
    assert availability["server_available"] is True
    assert availability["cli_available"] is True


def test_runtime_validates_binary_and_model_paths(tmp_path: Path) -> None:
    missing_binary = load_config({"llama_cpp_server_path": str(tmp_path / "missing-server")})
    missing_runtime = LlamaCppRuntime(missing_binary)
    assert missing_runtime.detect()["available"] is False

    valid_runtime = LlamaCppRuntime(load_config({"llama_cpp_server_path": sys.executable}))
    missing_model = valid_runtime.validate_model_path(str(tmp_path / "missing.gguf"))
    assert missing_model["valid"] is False
    assert "does not exist" in missing_model["error"]

    wrong_model = tmp_path / "model.bin"
    wrong_model.write_text("not gguf")
    wrong = valid_runtime.validate_model_path(str(wrong_model))
    assert wrong["valid"] is False
    assert "GGUF" in wrong["error"]


def test_compute_verify_local_records_real_llama_compatibility(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    env = local_env(home)
    run_cli(home, "login", "--email", "ops@acme.test", extra_env=env)
    run_cli(home, "org", "create", "acme-ai", extra_env=env)
    run_cli(home, "project", "create", "prod-chat", extra_env=env)

    output = run_cli(home, "compute", "verify", "local", extra_env=env)

    assert "Pool local certified" in output
    assert "llama.cpp" in output
    state = read_state(home)
    pool = state["compute_pools"]["local"]
    assert pool["kind"] == "local"
    assert pool["certified"] is True
    records = [record for record in state["compatibility_records"] if record["pool"] == "local"]
    assert records[0]["runtime"] == "llama.cpp"
    assert records[0]["status"] == "certified"
    assert records[0]["real"] is True


def test_local_benchmark_marks_real_for_gguf_and_simulated_for_non_gguf(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    env = local_env(home)
    model_path = home / "tiny.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"GGUF-test-model")
    run_cli(home, "login", "--email", "ops@acme.test", extra_env=env)
    run_cli(home, "org", "create", "acme-ai", extra_env=env)
    run_cli(home, "project", "create", "prod-chat", extra_env=env)
    run_cli(home, "compute", "verify", "local", extra_env=env)
    run_cli(home, "model", "register", "tiny-gguf", "--source", str(model_path), "--format", "gguf", extra_env=env)
    run_cli(home, "model", "register", "tiny-safe", "--source", "hf:test/Tiny-7B", "--format", "safetensors", extra_env=env)

    real_output = run_cli(home, "benchmark", "tiny-gguf", "--targets", "local", "--duration", "1m", extra_env=env)
    simulated_output = run_cli(home, "benchmark", "tiny-safe", "--targets", "local", "--duration", "1m", extra_env=env)

    assert "simulated=false" in real_output
    assert "simulated=true" in simulated_output
    state = read_state(home)
    real = state["benchmarks"]["tiny-gguf"]["results"][0]
    assert real["simulated"] is False
    assert real["tokens_generated"] == 3
    assert real["token_count_method"] == "upstream_usage"
    assert real["benchmark_prompt"]
    assert real["startup_time_ms"] >= 0
    assert Path(real["logs_path"]).exists()
    assert state["benchmarks"]["tiny-safe"]["results"][0]["simulated"] is True


def test_local_provider_launch_health_stop_and_log(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    config = load_config(
        {
            "llama_cpp_server_path": sys.executable,
            "llama_cpp_server_args": str(FAKE_LLAMA),
            "llama_cpp_health_path": "/health",
            "model_cache_path": str(home / "models"),
            "local_runtime_host": "127.0.0.1",
            "local_runtime_port_start": 19100,
            "local_runtime_port_end": 19250,
        }
    )
    provider = LocalProvider(config)
    process = provider.launch_llama_server("demo", str(home / "tiny.gguf"), 19120)
    try:
        assert process["pid"] > 0
        assert process["provider"] == "local"
        assert process["model_path"] == str(home / "tiny.gguf")
        assert process["simulated"] is False
        assert process["health_check_type"] == "http"
        assert process["upstream_url"] == "http://127.0.0.1:19120"
        assert "--ctx-size" in process["command"]
        assert Path(process["logs_path"]).exists()
        assert provider.health_check(process) is True
    finally:
        provider.stop(process)

    assert provider.health_check(process) is False


def test_serve_local_llama_stores_process_metadata_and_stop_cleans_up(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    env = local_env(home)
    model_path = home / "tiny.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"GGUF-test-model")
    run_cli(home, "login", "--email", "ops@acme.test", extra_env=env)
    run_cli(home, "org", "create", "acme-ai", extra_env=env)
    run_cli(home, "project", "create", "prod-chat", extra_env=env)
    run_cli(home, "compute", "verify", "local", extra_env=env)
    run_cli(home, "model", "register", "tiny-gguf", "--source", str(model_path), "--format", "gguf", extra_env=env)
    run_cli(home, "benchmark", "tiny-gguf", "--targets", "local", "--duration", "1m", extra_env=env)
    run_cli(home, "policy", "create", "local-policy", "--objective", "fastest", "--max-p95", "2000ms", extra_env=env)

    output = run_cli(home, "serve", "tiny-gguf", "--name", "local-chat", "--policy", "local-policy", extra_env=env)

    assert "Deployment local-chat is live" in output
    state = read_state(home)
    process = state["deployments"]["local-chat"]["runtime_process"]
    assert process["pid"] > 0
    assert process["health"] == "healthy"
    assert process["model_path"] == str(model_path)
    assert process["provider"] == "local"
    assert process["upstream_url"] == f"http://{process['host']}:{process['port']}"
    assert state["deployments"]["local-chat"]["routes"][0]["upstream_url"] == process["upstream_url"]
    assert state["deployments"]["local-chat"]["routes"][0]["simulated"] is False
    assert Path(process["logs_path"]).exists()
    urllib.request.urlopen(f"http://{process['host']}:{process['port']}/health", timeout=5)

    ps_output = run_cli(home, "runtime", "ps", extra_env=env)
    assert "local-chat" in ps_output
    assert str(process["pid"]) in ps_output

    stop_output = run_cli(home, "deployments", "stop", "local-chat", extra_env=env)
    assert "Stopped deployment local-chat" in stop_output
    stopped = read_state(home)["deployments"]["local-chat"]["runtime_process"]
    assert stopped["health"] == "stopped"
    time.sleep(0.1)
    process_check = subprocess.run(["ps", "-p", str(process["pid"])], text=True, capture_output=True, check=False)
    assert process_check.returncode != 0


def test_runtime_cleanup_marks_stale_processes(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    env = local_env(home)
    run_cli(home, "login", "--email", "ops@acme.test", extra_env=env)
    run_cli(home, "org", "create", "acme-ai", extra_env=env)
    run_cli(home, "project", "create", "prod-chat", extra_env=env)
    run_cli(home, "compute", "verify", "local", extra_env=env)
    state_path = home / "state.json"
    state = read_state(home)
    state["deployments"]["stale-local"] = {
        "name": "stale-local",
        "health": "healthy",
        "routes": [{"pool": "local", "status": "healthy"}],
        "runtime_process": {
            "pid": 99999999,
            "health": "healthy",
            "host": "127.0.0.1",
            "port": 19999,
            "runtime": "llama.cpp",
            "logs_path": str(home / "logs" / "stale.log"),
        },
    }
    state_path.write_text(json.dumps(state))

    output = run_cli(home, "runtime", "cleanup", extra_env=env)

    assert "stale-local" in output
    cleaned = read_state(home)["deployments"]["stale-local"]
    assert cleaned["runtime_process"]["health"] == "stale"
    assert cleaned["routes"][0]["status"] == "stale"
