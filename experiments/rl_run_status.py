from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from experiments.audit_rl_result import audit_result
except ModuleNotFoundError:
    from audit_rl_result import audit_result


DEFAULT_ARTIFACT_DIR = Path(".anygpu/rl_runs")
SKYPILOT_ENDPOINT_ENV = "SKYPILOT_API_SERVER_ENDPOINT"
RL_RESULT_KEYS = {"device", "samples", "initial_policy_eval", "trained_policy_eval", "improvement", "train"}


def _run_command(command: list[str], timeout: float = 5.0) -> dict[str, Any]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=timeout)
    except FileNotFoundError:
        return {"available": False, "error": f"{command[0]} not found"}
    except subprocess.TimeoutExpired:
        return {"available": False, "error": "command timed out"}
    return {
        "available": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _check_skypilot_health(endpoint: str, timeout: float = 5.0) -> dict[str, Any]:
    url = endpoint.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"available": False, "endpoint": endpoint, "error": str(exc)}
    return {
        "available": payload.get("status") == "healthy",
        "endpoint": endpoint,
        "health": payload,
    }


def summarize_status(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    *,
    provider_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifacts = []
    for path in sorted(artifact_dir.glob("*.json")):
        try:
            result = json.loads(path.read_text())
            if not RL_RESULT_KEYS.issubset(result):
                continue
            gpu_audit = audit_result(result, require_cuda=True)
            permissive_audit = audit_result(result, require_cuda=False)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            artifacts.append({"path": str(path), "valid": False, "error": str(exc)})
            continue
        artifacts.append(
            {
                "path": str(path),
                "valid": True,
                "gpu_completion": gpu_audit,
                "learning_signal": permissive_audit,
            }
        )

    if provider_status is None:
        modal_profile = _run_command(["modal", "profile", "current"]) if shutil.which("modal") else {"available": False}
        skypilot_endpoint = os.environ.get(SKYPILOT_ENDPOINT_ENV, "http://127.0.0.1:8080")
        skypilot_health = _check_skypilot_health(skypilot_endpoint)
        provider_status = {
            "modal": {
                "cli_profile": modal_profile,
                "token_env_present": bool(os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET")),
            },
            "skypilot": {
                "api_server": skypilot_health,
            },
        }
    complete = any(item.get("gpu_completion", {}).get("passed") for item in artifacts if item.get("valid"))

    return {
        "complete": complete,
        "artifacts": artifacts,
        "providers": {
            "modal": {
                **provider_status["modal"],
                "run_command": (
                    "modal run experiments/modal_rl_smoke.py --gpu T4 --updates 3 --n-envs 4096 "
                    "--rollout-steps 16 --ppo-epochs 2 --minibatch-size 8192 "
                    "--target-success-rate 0.9 --min-success-delta 0.25 "
                    "--output .anygpu/rl_runs/modal_rl_t4_run.json"
                ),
            },
            "skypilot": {
                **provider_status["skypilot"],
                "run_command": "sky launch -y experiments/skypilot_rl_smoke.yaml",
                "teardown_command": "sky down -y nozomio-rl-gpu-smoke",
            },
        },
        "missing": [] if complete else ["No artifact currently passes CUDA/GPU completion audit."],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report RL GPU smoke readiness and completion status.")
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()
    status = summarize_status(args.artifact_dir)
    print(json.dumps(status, indent=2, sort_keys=True))
    if not status["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
