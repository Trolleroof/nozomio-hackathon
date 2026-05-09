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


def test_deploy_target_kubernetes_generates_vllm_manifests(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"

    output = run_cli(
        home,
        "deploy",
        "qwen-prod",
        "--model",
        "hf:Qwen/Qwen2.5-7B-Instruct",
        "--runtime",
        "vllm",
        "--target",
        "kubernetes",
        "--gpu",
        "nvidia-l4",
        "--namespace",
        "anygpu",
        "--replicas",
        "2",
    )

    assert "apiVersion: apps/v1" in output
    assert "kind: Deployment" in output
    assert "name: qwen-prod-vllm" in output
    assert "namespace: anygpu" in output
    assert "replicas: 2" in output
    assert "image: vllm/vllm-openai:latest" in output
    assert "- --model" in output
    assert "- Qwen/Qwen2.5-7B-Instruct" in output
    assert "nvidia.com/gpu: 1" in output
    assert "anygpu.ai/gpu: nvidia-l4" in output
    assert "kind: Service" in output
    assert "kind: ConfigMap" in output
    assert "kind: PersistentVolumeClaim" in output


def test_deploy_target_kubernetes_generates_llama_cpp_manifests(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    model_path = tmp_path / "models" / "qwen.gguf"
    model_path.parent.mkdir()
    model_path.write_bytes(b"GGUF")

    output = run_cli(
        home,
        "deploy",
        "qwen-gguf",
        "--model",
        str(model_path),
        "--runtime",
        "llama.cpp",
        "--target",
        "kubernetes",
        "--gpu",
        "none",
    )

    assert "name: qwen-gguf-llama-cpp" in output
    assert "image: ghcr.io/ggml-org/llama.cpp:server" in output
    assert "- -m" in output
    assert "- /models/qwen.gguf" in output
    assert "containerPort: 8080" in output
    assert "mountPath: /models" in output
