from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from experiments.audit_rl_result import audit_result


JSON = dict[str, Any]


def execute_modal_rl_smoke(
    *,
    run_id: str,
    repo_root: Path | str,
    output_dir: Path | str,
    gpu: str = "T4",
    updates: int = 3,
    n_envs: int = 4096,
    rollout_steps: int = 16,
    ppo_epochs: int = 2,
    minibatch_size: int = 8192,
    target_success_rate: float = 0.90,
    min_success_delta: float = 0.25,
) -> JSON:
    repo = Path(repo_root)
    artifact_dir = Path(output_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    safe_run_id = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in run_id)
    output_path = artifact_dir / f"modal_rl_{safe_run_id}.json"

    command = [
        "modal",
        "run",
        "experiments/modal_rl_smoke.py",
        "--gpu",
        gpu,
        "--updates",
        str(updates),
        "--n-envs",
        str(n_envs),
        "--rollout-steps",
        str(rollout_steps),
        "--ppo-epochs",
        str(ppo_epochs),
        "--minibatch-size",
        str(minibatch_size),
        "--target-success-rate",
        str(target_success_rate),
        "--min-success-delta",
        str(min_success_delta),
        "--output",
        str(output_path),
    ]
    completed = subprocess.run(command, cwd=repo, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "modal run failed"
        raise RuntimeError(stderr)
    if not output_path.exists():
        raise RuntimeError(f"Modal run completed but did not write artifact {output_path}")

    result = json.loads(output_path.read_text())
    audit = audit_result(result, require_cuda=True)
    metadata = _artifact_metadata(result, audit)
    summary = (
        f"Modal RL smoke passed on {metadata['gpu_name']}."
        if audit["passed"]
        else f"Modal RL smoke failed on {result.get('device', 'unknown device')}."
    )

    return {
        "command": command,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "result": result,
        "audit": audit,
        "artifact": {
            "path": str(output_path),
            "uri": output_path.resolve().as_uri(),
            "metadata": metadata,
        },
        "training_event": {
            "phase": "train",
            "rollout_count": updates,
            "reward_mean": result.get("improvement", {}).get("mean_return_delta"),
            "success_rate": result.get("trained_policy_eval", {}).get("success_rate"),
            "cost_burn_usd": result.get("cost", {}).get("estimated_gpu_cost_usd"),
            "gpu_name": result.get("gpu_name"),
            "message": summary,
        },
        "compute_memory": {
            "provider": "modal",
            "gpu_name": result.get("gpu_name"),
            "event_type": "verified_training_run",
            "status": "passed" if audit["passed"] else "failed",
            "summary": summary,
            "pricing": {
                "price_per_hr": result.get("cost", {}).get("estimated_gpu_usd_per_hour"),
                "measured_cost_usd": result.get("cost", {}).get("estimated_gpu_cost_usd"),
            },
            "compatibility": {
                "algorithm": "ppo",
                "runtime": "torch-vectorized",
                "device": result.get("device"),
            },
        },
    }


def _artifact_metadata(result: JSON, audit: JSON) -> JSON:
    improvement = result.get("improvement", {})
    trained = result.get("trained_policy_eval", {})
    cost = result.get("cost", {})
    train = result.get("train", {})
    return {
        "passed": bool(audit.get("passed")),
        "device": result.get("device"),
        "gpu_name": result.get("gpu_name"),
        "cost_usd": cost.get("estimated_gpu_cost_usd"),
        "reward_delta": improvement.get("mean_return_delta"),
        "success_rate_delta": improvement.get("success_rate_delta"),
        "trained_success_rate": trained.get("success_rate"),
        "samples": result.get("samples"),
        "duration_sec": train.get("duration_sec"),
    }
