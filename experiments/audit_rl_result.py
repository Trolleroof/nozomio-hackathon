from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def audit_result(
    result: dict[str, Any],
    *,
    require_cuda: bool = True,
    min_success_rate: float = 0.90,
    min_success_delta: float = 0.25,
    require_positive_return_delta: bool = True,
) -> dict[str, Any]:
    device = result.get("device")
    trained = result.get("trained_policy_eval", {})
    improvement = result.get("improvement", {})
    checks = {
        "ran_on_cuda": device == "cuda",
        "has_gpu_name": bool(result.get("gpu_name")),
        "trained_success_rate": trained.get("success_rate", 0.0) >= min_success_rate,
        "success_rate_improved": improvement.get("success_rate_delta", 0.0) >= min_success_delta,
        "mean_return_improved": improvement.get("mean_return_delta", 0.0) > 0,
        "recorded_samples": result.get("samples", 0) > 0,
        "recorded_runtime": result.get("train", {}).get("duration_sec", 0.0) > 0,
    }
    if not require_cuda:
        checks["ran_on_cuda"] = True
        checks["has_gpu_name"] = True
    if not require_positive_return_delta:
        checks["mean_return_improved"] = True

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "summary": {
            "device": device,
            "gpu_name": result.get("gpu_name"),
            "initial_success_rate": result.get("initial_policy_eval", {}).get("success_rate"),
            "trained_success_rate": trained.get("success_rate"),
            "success_rate_delta": improvement.get("success_rate_delta"),
            "mean_return_delta": improvement.get("mean_return_delta"),
            "samples": result.get("samples"),
            "duration_sec": result.get("train", {}).get("duration_sec"),
            "estimated_gpu_cost_usd": result.get("cost", {}).get("estimated_gpu_cost_usd"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an RL smoke result artifact.")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--min-success-rate", type=float, default=0.90)
    parser.add_argument("--min-success-delta", type=float, default=0.25)
    args = parser.parse_args()

    result = json.loads(args.artifact.read_text())
    audit = audit_result(
        result,
        require_cuda=not args.allow_cpu,
        min_success_rate=args.min_success_rate,
        min_success_delta=args.min_success_delta,
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
