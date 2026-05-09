import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from anygpu.provider import KubernetesProvider


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


def read_state(home: Path) -> dict:
    with (home / "state.json").open() as handle:
        return json.load(handle)


def make_fake_kubectl(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kubectl = bin_dir / "kubectl"
    nodes = {
        "items": [
            {
                "metadata": {
                    "name": "gpu-node-1",
                    "labels": {
                        "nvidia.com/gpu.product": "NVIDIA-L4",
                        "anygpu.ai/gpu-memory-gb": "24",
                    },
                },
                "status": {
                    "capacity": {"cpu": "32", "memory": "128Gi", "nvidia.com/gpu": "4"},
                    "allocatable": {"cpu": "30", "memory": "120Gi", "nvidia.com/gpu": "3"},
                    "nodeInfo": {"kubeletVersion": "v1.34.1", "containerRuntimeVersion": "containerd://2.0.0"},
                    "conditions": [{"type": "Ready", "status": "True"}],
                },
            }
        ]
    }
    kubectl.write_text(
        f"""#!/bin/sh
args="$*"
if [ "$args" = "--context prod-cluster get nodes -o json" ]; then
  cat <<'JSON'
{json.dumps(nodes)}
JSON
  exit 0
fi
if [ "$args" = "--context prod-cluster get namespace anygpu -o json" ]; then
  printf '%s\\n' '{{"metadata":{{"name":"anygpu"}}}}'
  exit 0
fi
printf '%s\\n' "unexpected kubectl args: $args" >&2
exit 1
"""
    )
    kubectl.chmod(kubectl.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def connect_project(home: Path, env: dict[str, str]) -> None:
    run_cli(home, "login", extra_env=env)
    run_cli(home, "org", "create", "acme-ai", extra_env=env)
    run_cli(home, "project", "create", "prod-chat", extra_env=env)
    run_cli(
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
        extra_env=env,
    )


def test_kubernetes_provider_inventory_schema_from_kubectl(tmp_path: Path) -> None:
    fake_bin = make_fake_kubectl(tmp_path)
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

    provider = KubernetesProvider("prod-cluster", "anygpu", env=env)
    inventory = provider.list_inventory("acme-prod-k8s")

    assert inventory["provider"] == "kubernetes"
    assert inventory["cluster"] == "acme-prod-k8s"
    assert inventory["context"] == "prod-cluster"
    assert inventory["namespace"] == "anygpu"
    assert inventory["status"] == "available"
    assert inventory["nodes"][0]["name"] == "gpu-node-1"
    assert inventory["nodes"][0]["available"] is True
    assert inventory["nodes"][0]["accelerators"] == [
        {
            "vendor": "nvidia",
            "name": "NVIDIA L4",
            "count": 4,
            "allocatable": 3,
            "memory_gb": 24,
            "resource": "nvidia.com/gpu",
        }
    ]
    assert set(inventory["nodes"][0]["runtimes"]) >= {"vllm", "sglang", "pytorch", "llama.cpp"}
    assert inventory["checks"][0]["status"] == "pass"


def test_compute_inventory_kubernetes_cli_records_real_inventory(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    fake_bin = make_fake_kubectl(tmp_path)
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}
    connect_project(home, env)

    output = run_cli(home, "compute", "inventory", "acme-prod-k8s", extra_env=env)
    inventory = json.loads(output)

    assert inventory["provider"] == "kubernetes"
    assert inventory["status"] == "available"
    assert inventory["nodes"][0]["accelerators"][0]["name"] == "NVIDIA L4"
    assert inventory["runtime_support"] == ["vllm", "sglang", "pytorch", "llama.cpp"]

    state = read_state(home)
    pool = state["compute_pools"]["acme-prod-k8s"]
    assert pool["hardware"] == "NVIDIA L4"
    assert pool["capacity"] == 4
    assert pool["max_vram_gb"] == 24
    assert pool["status"] == "available"


def test_compute_verify_kubernetes_records_real_compatibility_when_context_available(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    fake_bin = make_fake_kubectl(tmp_path)
    env = {"PATH": f"{fake_bin}:{os.environ['PATH']}"}
    connect_project(home, env)

    output = run_cli(home, "compute", "verify", "acme-prod-k8s", extra_env=env)

    assert "Pool acme-prod-k8s certified" in output
    assert "vllm" in output
    assert "false" in output
    state = read_state(home)
    pool = state["compute_pools"]["acme-prod-k8s"]
    assert pool["status"] == "certified"
    assert pool["certified"] is True
    assert pool["verification_checks"][0]["name"] == "list kubernetes nodes"
    assert pool["verification_checks"][0]["status"] == "pass"
    records = [record for record in state["compatibility_records"] if record["pool"] == "acme-prod-k8s"]
    assert records
    assert all(record["simulated"] is False for record in records)
    assert {record["runtime"] for record in records} >= {"vllm", "llama.cpp", "pytorch"}


def test_compute_inventory_kubernetes_unavailable_schema_without_kubectl(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    env = {"PATH": "/nonexistent"}
    connect_project(home, env)

    output = run_cli(home, "compute", "inventory", "acme-prod-k8s", extra_env=env)
    inventory = json.loads(output)

    assert inventory["provider"] == "kubernetes"
    assert inventory["status"] == "unavailable"
    assert inventory["nodes"] == []
    assert inventory["checks"][0]["status"] == "fail"
    assert inventory["error"]


def test_compute_verify_kubernetes_falls_back_to_simulated_when_context_unavailable(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    env = {"PATH": "/nonexistent"}
    connect_project(home, env)

    output = run_cli(home, "compute", "verify", "acme-prod-k8s", extra_env=env)

    assert "Pool acme-prod-k8s certified" in output
    assert "vllm" in output
    assert "true" in output
    state = read_state(home)
    pool = state["compute_pools"]["acme-prod-k8s"]
    assert pool["status"] == "simulated"
    assert pool["certified"] is True
    assert pool["verification_checks"][0]["status"] == "fail"
    records = [record for record in state["compatibility_records"] if record["pool"] == "acme-prod-k8s"]
    assert records
    assert all(record["simulated"] is True for record in records)
