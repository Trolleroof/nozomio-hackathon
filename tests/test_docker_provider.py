from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from anygpu.provider import DockerProvider


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
    result = subprocess.run(
        [sys.executable, "-m", "anygpu", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result


def make_fake_docker(tmp_path: Path, nvidia_smi_output: str | None = None) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        f"""#!/bin/sh
pid_file="$ANYGPU_FAKE_DOCKER_PID_FILE"
host_port=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "-p" ]; then
    host_port="${{arg%%:*}}"
  fi
  prev="$arg"
done
if [ "$1" = "version" ]; then
  printf '%s\\n' 'Docker version 27.3.1, build test'
  exit 0
fi
if [ "$1" = "info" ]; then
  printf '%s\\n' '{{"nvidia":{{}}}}'
  exit 0
fi
if [ "$1" = "run" ]; then
  if [ -n "$ANYGPU_FAKE_DOCKER_LOG" ]; then
    printf '%s\\n' "$*" >> "$ANYGPU_FAKE_DOCKER_LOG"
  fi
  if [ -n "$ANYGPU_FAKE_DOCKER_HTTP_SERVER" ] && [ -n "$host_port" ]; then
    sh -c "$ANYGPU_FAKE_DOCKER_HTTP_SERVER --host 127.0.0.1 --port $host_port" >/dev/null 2>&1 &
    if [ -n "$pid_file" ]; then
      printf '%s\\n' "$!" > "$pid_file"
    fi
  fi
  printf '%s\\n' 'container-qwen-local'
  exit 0
fi
if [ "$1" = "inspect" ]; then
  printf '%s\\n' '{{"Status":"running","Health":{{"Status":"healthy"}}}}'
  exit 0
fi
if [ "$1" = "logs" ]; then
  printf '%s\\n' 'fake llama.cpp container log'
  exit 0
fi
if [ "$1" = "stop" ]; then
  if [ -n "$pid_file" ] && [ -f "$pid_file" ]; then
    kill "$(cat "$pid_file")" >/dev/null 2>&1 || true
    rm -f "$pid_file"
  fi
  printf '%s\\n' "$2"
  exit 0
fi
if [ "$1" = "rm" ]; then
  printf '%s\\n' "$2"
  exit 0
fi
exit 1
"""
    )
    docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
    if nvidia_smi_output is not None:
        nvidia_smi = bin_dir / "nvidia-smi"
        nvidia_smi.write_text(
            f"""#!/bin/sh
printf '%s\\n' '{nvidia_smi_output}'
"""
        )
        nvidia_smi.chmod(nvidia_smi.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def read_state(home: Path) -> dict:
    with (home / "state.json").open() as handle:
        return json.load(handle)


def test_docker_provider_inventory_schema_with_detected_gpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ['PATH']}")

    inventory = DockerProvider({}).list_inventory()

    assert inventory["provider"] == "docker"
    assert inventory["node_id"] == "local"
    assert inventory["docker"]["available"] is True
    assert inventory["gpus"] == [
        {
            "vendor": "nvidia",
            "name": "NVIDIA GeForce RTX 4090",
            "memory_gb": 24,
            "driver": "550.54.14",
            "cuda": "available",
        }
    ]
    assert set(inventory["runtimes_supported"]) >= {"vllm", "llama.cpp", "pytorch"}


def test_docker_provider_inventory_schema_when_docker_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")

    inventory = DockerProvider({}).list_inventory()

    assert inventory["provider"] == "docker"
    assert inventory["node_id"] == "local"
    assert inventory["docker"]["available"] is False
    assert inventory["gpus"] == []
    assert set(inventory["runtimes_supported"]) >= {"llama.cpp", "pytorch", "vllm"}


def test_docker_provider_runtime_interface_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    provider = DockerProvider({})
    model_path = tmp_path / "qwen.gguf"
    model_path.write_bytes(b"GGUF")

    handle = provider.create_runtime({"name": "qwen-local", "runtime": "llama.cpp", "model_path": str(model_path)})
    stopped = provider.stop_runtime("qwen-local")
    inspected = provider.inspect_runtime("qwen-local")
    health = provider.health_check("qwen-local")

    assert handle["provider"] == "docker"
    assert handle["status"] == "created"
    assert stopped["status"] == "stop_failed"
    assert inspected["status"] == "unknown"
    assert health["healthy"] is False


def test_compute_connect_docker_and_inventory_cli(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    connected = run_cli(home, "compute", "connect", "docker", "--name", "local-docker", extra_env=env)
    assert "Registered Docker pool local-docker" in connected

    output = run_cli(home, "compute", "inventory", "local-docker", extra_env=env)
    inventory = json.loads(output)

    assert inventory["provider"] == "docker"
    assert inventory["node_id"] == "local"
    assert inventory["gpus"][0]["memory_gb"] == 24
    assert "vllm" in inventory["runtimes_supported"]


def test_serve_start_ps_logs_stop_docker_llama_cpp(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    model_path = tmp_path / "models" / "qwen.gguf"
    model_path.parent.mkdir()
    model_path.write_bytes(b"GGUF test model")
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    docker_log = tmp_path / "docker-argv.log"
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ANYGPU_FAKE_DOCKER_LOG": str(docker_log),
    }

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "docker", "--name", "local-docker", extra_env=env)

    started = run_cli(
        home,
        "serve",
        "start",
        "qwen-local",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--compute",
        "local-docker",
        extra_env=env,
    )
    assert "Started qwen-local on local-docker" in started
    assert "http://127.0.0.1:8080/v1/chat/completions" in started

    state = read_state(home)
    deployment = state["deployments"]["qwen-local"]
    process = deployment["runtime_process"]
    assert deployment["provider"] == "docker"
    assert deployment["compute"] == "local-docker"
    assert deployment["health"] == "healthy"
    assert process["container_id"] == "container-qwen-local"
    assert process["container_name"] == "anygpu-qwen-local"
    assert process["port"] == 8080
    assert process["simulated"] is False
    assert deployment["routes"][0]["upstream_url"] == "http://127.0.0.1:8080"

    docker_args = docker_log.read_text()
    assert "run -d" in docker_args
    assert "-p 8080:8080" in docker_args
    assert "-m /models/qwen.gguf" in docker_args

    ps = run_cli(home, "serve", "ps", extra_env=env)
    assert "qwen-local" in ps
    assert "healthy" in ps
    assert "8080" in ps

    status = run_cli(home, "deployments", "status", "qwen-local", extra_env=env)
    assert "Runtime process:" in status
    assert "container: container-qwen-local" in status
    assert "container_name: anygpu-qwen-local" in status
    assert "port: 8080" in status

    logs = run_cli(home, "serve", "logs", "qwen-local", extra_env=env)
    assert "fake llama.cpp container log" in logs

    stopped = run_cli(home, "serve", "stop", "qwen-local", extra_env=env)
    assert "Stopped qwen-local" in stopped
    assert read_state(home)["deployments"]["qwen-local"]["health"] == "stopped"


def test_serve_start_docker_vllm_hf_model(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    docker_log = tmp_path / "docker-argv.log"
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ANYGPU_FAKE_DOCKER_LOG": str(docker_log),
    }

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "docker", "--name", "local-docker", extra_env=env)

    started = run_cli(
        home,
        "serve",
        "start",
        "qwen-vllm",
        "--model",
        "hf:Qwen/Qwen2.5-7B-Instruct",
        "--runtime",
        "vllm",
        "--compute",
        "local-docker",
        extra_env=env,
    )

    assert "Started qwen-vllm on local-docker" in started
    deployment = read_state(home)["deployments"]["qwen-vllm"]
    process = deployment["runtime_process"]
    assert f"http://127.0.0.1:{process['port']}/v1/chat/completions" in started
    assert deployment["runtime"] == "vllm"
    assert process["image"] == "vllm/vllm-openai:latest"
    assert process["container_port"] == 8000
    assert process["model_source"] == "hf:Qwen/Qwen2.5-7B-Instruct"
    assert deployment["routes"][0]["upstream_url"] == f"http://127.0.0.1:{process['port']}"

    docker_args = docker_log.read_text()
    assert "--gpus all" in docker_args
    assert f"-p {process['port']}:8000" in docker_args
    assert "vllm/vllm-openai:latest" in docker_args
    assert "--model Qwen/Qwen2.5-7B-Instruct" in docker_args


def test_serve_start_docker_unavailable_is_clean_error(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    model_path = tmp_path / "models" / "qwen.gguf"
    model_path.parent.mkdir()
    model_path.write_bytes(b"GGUF test model")
    env = {"PATH": "/nonexistent"}

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "docker", "--name", "local-docker", extra_env=env)

    result = run_cli_raw(
        home,
        "serve",
        "start",
        "qwen-local",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--compute",
        "local-docker",
        extra_env=env,
    )

    assert result.returncode == 2
    assert "error: Docker is unavailable:" in result.stderr
    assert "Traceback" not in result.stderr


def test_benchmark_run_docker_llama_cpp_records_real_measurement(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    model_path = tmp_path / "models" / "qwen.gguf"
    model_path.parent.mkdir()
    model_path.write_bytes(b"GGUF test model")
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ANYGPU_FAKE_DOCKER_HTTP_SERVER": f"{sys.executable} {ROOT / 'tests' / 'fixtures' / 'fake_llama_server.py'}",
        "ANYGPU_FAKE_DOCKER_PID_FILE": str(tmp_path / "fake-server.pid"),
    }

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "docker", "--name", "local-docker", extra_env=env)

    output = run_cli(
        home,
        "benchmark",
        "run",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--compute",
        "local-docker",
        "--profile",
        "latency-chat",
        extra_env=env,
    )

    assert "Benchmark bench_" in output
    assert "success: true" in output
    assert "simulated: false" in output
    state = read_state(home)
    result = state["benchmark_results"][-1]
    assert result["model"] == str(model_path)
    assert result["runtime"] == "llama.cpp"
    assert result["compute"] == "local-docker"
    assert result["profile"] == "latency-chat"
    assert result["success"] is True
    assert result["simulated"] is False
    assert result["tokens_per_second_p50"] > 0
    assert result["ttft_ms_p50"] >= 0
    assert result["hardware"]["accelerator_name"] == "NVIDIA GeForce RTX 4090"

    model_id = result["model_id"]
    runtime_id = result["runtime_id"]
    hardware_id = result["hardware_id"]
    assert state["hardware_nodes"][hardware_id]["accelerator_name"] == "NVIDIA GeForce RTX 4090"
    assert state["model_records"][model_id]["source"] == str(model_path)
    assert state["runtime_profiles"][runtime_id]["name"] == "llama.cpp"
    compatibility = state["compatibility_records"][-1]
    assert compatibility["model_id"] == model_id
    assert compatibility["runtime_id"] == runtime_id
    assert compatibility["hardware_id"] == hardware_id
    assert compatibility["status"] == "verified"
    assert compatibility["source"] == "benchmark"
    assert compatibility["benchmark_result_id"] == result["id"]


def test_benchmark_run_failed_measurement_records_failed_compatibility(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    model_path = tmp_path / "models" / "qwen.gguf"
    model_path.parent.mkdir()
    model_path.write_bytes(b"GGUF test model")
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "docker", "--name", "local-docker", extra_env=env)

    output = run_cli(
        home,
        "benchmark",
        "run",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--compute",
        "local-docker",
        "--profile",
        "latency-chat",
        extra_env=env,
    )

    assert "success: false" in output
    assert "simulated: false" in output
    state = read_state(home)
    result = state["benchmark_results"][-1]
    compatibility = state["compatibility_records"][-1]
    assert result["success"] is False
    assert result["error"]
    assert compatibility["status"] == "failed"
    assert compatibility["source"] == "benchmark"
    assert compatibility["benchmark_result_id"] == result["id"]
    assert compatibility["error"] == result["error"]


def test_deploy_uses_verified_benchmark_compatibility_and_explain(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    model_path = tmp_path / "models" / "qwen.gguf"
    model_path.parent.mkdir()
    model_path.write_bytes(b"GGUF test model")
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ANYGPU_FAKE_DOCKER_HTTP_SERVER": f"{sys.executable} {ROOT / 'tests' / 'fixtures' / 'fake_llama_server.py'}",
        "ANYGPU_FAKE_DOCKER_PID_FILE": str(tmp_path / "fake-server.pid"),
    }

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "docker", "--name", "local-docker", extra_env=env)
    run_cli(
        home,
        "benchmark",
        "run",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--compute",
        "local-docker",
        "--profile",
        "latency-chat",
        extra_env=env,
    )

    deployed = run_cli(
        home,
        "deploy",
        "qwen-prod",
        "--model",
        str(model_path),
        "--sla",
        "latency",
        "--strategy",
        "cheapest-compatible",
        extra_env=env,
    )

    assert "Deployment qwen-prod scheduled" in deployed
    assert "Selected runtime: llama.cpp" in deployed
    assert "Selected provider: docker" in deployed
    assert "verified benchmark" in deployed

    state = read_state(home)
    deployment = state["deployments"]["qwen-prod"]
    assert deployment["kind"] == "scheduled"
    assert deployment["model"] == str(model_path)
    assert deployment["scheduler_decision"]["selected"]["runtime"] == "llama.cpp"
    assert deployment["scheduler_decision"]["selected"]["provider"] == "docker"
    assert deployment["scheduler_decision"]["selected"]["compatibility_status"] == "verified"
    assert deployment["routes"][0]["simulated"] is False

    explanation = run_cli(home, "explain", "qwen-prod", extra_env=env)
    assert "Selected local-docker / NVIDIA GeForce RTX 4090 / llama.cpp" in explanation
    assert "verified benchmark exists" in explanation
    assert "estimated cost: local/free" in explanation


def test_cost_set_controls_scheduler_ranking_and_max_cost(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    model_path = tmp_path / "models" / "qwen.gguf"
    model_path.parent.mkdir()
    model_path.write_bytes(b"GGUF test model")
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    fast_env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ANYGPU_FAKE_DOCKER_HTTP_SERVER": f"{sys.executable} {ROOT / 'tests' / 'fixtures' / 'fake_llama_server.py'}",
        "ANYGPU_FAKE_DOCKER_PID_FILE": str(tmp_path / "fast.pid"),
    }
    slow_env = {
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "ANYGPU_FAKE_DOCKER_HTTP_SERVER": f"{sys.executable} {ROOT / 'tests' / 'fixtures' / 'fake_llama_server.py'}",
        "ANYGPU_FAKE_DOCKER_PID_FILE": str(tmp_path / "slow.pid"),
        "ANYGPU_DOCKER_RUNTIME_PORT_START": "8090",
        "ANYGPU_DOCKER_RUNTIME_PORT_END": "8099",
    }

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "docker", "--name", "fast-docker", extra_env=fast_env)
    run_cli(home, "compute", "connect", "docker", "--name", "cheap-docker", extra_env=slow_env)
    run_cli(home, "costs", "set", "--compute", "fast-docker", "--per-1m-tokens", "0.90", "--label", "fast-paid")
    run_cli(home, "costs", "set", "--compute", "cheap-docker", "--per-1m-tokens", "0.05", "--label", "cheap-local")

    run_cli(
        home,
        "benchmark",
        "run",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--compute",
        "fast-docker",
        "--profile",
        "latency-chat",
        extra_env=fast_env,
    )
    run_cli(
        home,
        "benchmark",
        "run",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--compute",
        "cheap-docker",
        "--profile",
        "latency-chat",
        extra_env=slow_env,
    )

    deployed = run_cli(
        home,
        "deploy",
        "qwen-prod",
        "--model",
        str(model_path),
        "--strategy",
        "cheapest-compatible",
        "--max-cost",
        "0.10/1m-tokens",
    )

    assert "Selected compute: cheap-docker" in deployed
    assert "estimated cost: cheap-local" in deployed
    state = read_state(home)
    selected = state["deployments"]["qwen-prod"]["scheduler_decision"]["selected"]
    assert selected["compute"] == "cheap-docker"
    assert selected["estimated_cost_per_1m_tokens"] == 0.05
    assert state["cost_records"]["docker:fast-docker"]["per_1m_tokens_usd"] == 0.90
    assert state["cost_records"]["docker:cheap-docker"]["label"] == "cheap-local"


def test_deploy_ignores_failed_compatibility_records(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    model_path = tmp_path / "models" / "qwen.gguf"
    model_path.parent.mkdir()
    model_path.write_bytes(b"GGUF test model")
    fake_bin = make_fake_docker(tmp_path, "NVIDIA GeForce RTX 4090, 24564, 550.54.14")
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "connect", "docker", "--name", "local-docker", extra_env=env)
    run_cli(
        home,
        "benchmark",
        "run",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--compute",
        "local-docker",
        "--profile",
        "latency-chat",
        extra_env=env,
    )

    result = run_cli_raw(
        home,
        "deploy",
        "qwen-prod",
        "--model",
        str(model_path),
        "--strategy",
        "cheapest-compatible",
        extra_env=env,
    )

    assert result.returncode == 2
    assert "No verified benchmark compatibility records match" in result.stderr
