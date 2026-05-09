import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(home: Path, *args: str) -> str:
    env = os.environ.copy()
    env["ANYGPU_HOME"] = str(home)
    env["PYTHONPATH"] = str(ROOT)
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


def test_full_lifecycle_deploys_verified_route(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"

    assert "Logged in" in run_cli(home, "login", "--email", "ops@acme.test")
    assert "Created org acme-ai" in run_cli(home, "org", "create", "acme-ai")
    assert "Created project prod-chat" in run_cli(home, "project", "create", "prod-chat")

    managed = run_cli(home, "compute", "use", "managed")
    assert "Managed compute enabled" in managed
    assert "nvidia-fast" in run_cli(home, "compute", "pools", "list")

    connected = run_cli(
        home,
        "compute",
        "connect",
        "kubernetes",
        "--name",
        "acme-prod-k8s",
        "--context",
        "prod-cluster",
        "--namespace",
        "anygpu",
    )
    assert "Registered BYOC pool acme-prod-k8s" in connected

    verified = run_cli(home, "compute", "verify", "acme-prod-k8s")
    assert "certified" in verified
    assert "vllm" in verified

    model = run_cli(
        home,
        "model",
        "register",
        "qwen-prod",
        "--source",
        "hf:Qwen/Qwen3-32B",
        "--format",
        "safetensors",
        "--task",
        "chat",
    )
    assert "Registered model qwen-prod" in model

    profile = run_cli(
        home,
        "profile",
        "qwen-prod",
        "--traffic",
        "50qps",
        "--context",
        "8192",
        "--output-tokens-p50",
        "512",
        "--latency-p95",
        "900ms",
    )
    assert "Candidate runtimes" in profile
    assert "vLLM CUDA" in profile

    benchmark = run_cli(
        home,
        "benchmark",
        "qwen-prod",
        "--policy",
        "balanced",
        "--targets",
        "managed:nvidia-fast,byoc:acme-prod-k8s",
        "--duration",
        "10m",
    )
    assert "Benchmark results" in benchmark
    assert "managed:nvidia-fast" in benchmark
    assert "byoc:acme-prod-k8s" in benchmark

    policy = run_cli(
        home,
        "policy",
        "create",
        "prod-chat-policy",
        "--objective",
        "cheapest",
        "--max-p95",
        "900ms",
        "--fallback",
        "required",
        "--regions",
        "us-west,us-east",
        "--data-residency",
        "us-only",
        "--prefer",
        "byoc",
        "--allow-managed-overflow",
        "true",
    )
    assert "Created policy prod-chat-policy" in policy

    deployed = run_cli(
        home,
        "serve",
        "qwen-prod",
        "--name",
        "support-chat-prod",
        "--policy",
        "prod-chat-policy",
        "--runtime",
        "auto",
        "--replicas",
        "min=2,max=20",
        "--endpoint",
        "openai",
    )
    assert "Deployment support-chat-prod is live" in deployed
    assert "Primary:" in deployed
    assert "Fallback:" in deployed

    status = run_cli(home, "deployments", "status", "support-chat-prod")
    assert "health: healthy" in status
    assert "p95:" in status

    costs = run_cli(home, "costs", "support-chat-prod")
    assert "effective cost" in costs

    optimize = run_cli(home, "optimize", "support-chat-prod")
    assert "New route found" in optimize or "No better route found" in optimize

    state = read_state(home)
    deployment = state["deployments"]["support-chat-prod"]
    assert deployment["model"] == "qwen-prod"
    assert deployment["routes"][0]["status"] == "healthy"
    assert state["compatibility_records"]
