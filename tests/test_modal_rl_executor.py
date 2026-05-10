import json
import subprocess
from pathlib import Path

from anygpu.modal_rl_executor import execute_modal_rl_smoke


def result_payload() -> dict:
    return {
        "passed": True,
        "device": "cuda",
        "gpu_name": "Tesla T4",
        "samples": 196608,
        "initial_policy_eval": {"success_rate": 0.0, "mean_return": -0.1},
        "trained_policy_eval": {"success_rate": 1.0, "mean_return": 1.15},
        "improvement": {"success_rate_delta": 1.0, "mean_return_delta": 1.25},
        "train": {"duration_sec": 7.0, "samples_per_second": 28086.8},
        "cost": {"estimated_gpu_cost_usd": 0.00115, "estimated_gpu_usd_per_hour": 0.59},
    }


def test_execute_modal_rl_smoke_runs_modal_and_audits_artifact(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def fake_run(command, *, cwd, text, capture_output, check):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "text": text,
                "capture_output": capture_output,
                "check": check,
            }
        )
        output_path = Path(command[command.index("--output") + 1])
        output_path.write_text(json.dumps(result_payload()))
        return subprocess.CompletedProcess(command, 0, stdout="artifact_path=" + str(output_path), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = execute_modal_rl_smoke(
        run_id="run_capsule_123",
        repo_root=tmp_path,
        output_dir=tmp_path,
        gpu="T4",
        updates=3,
        n_envs=4096,
        rollout_steps=16,
        ppo_epochs=2,
        minibatch_size=8192,
    )

    assert calls
    assert calls[0]["command"][:3] == ["modal", "run", "experiments/modal_rl_smoke.py"]
    assert result["audit"]["passed"] is True
    assert result["artifact"]["path"].endswith("modal_rl_run_capsule_123.json")
    assert result["artifact"]["metadata"]["success_rate_delta"] == 1.0
    assert result["training_event"]["success_rate"] == 1.0
    assert result["compute_memory"]["status"] == "passed"


def test_execute_modal_rl_smoke_raises_when_modal_command_fails(tmp_path: Path, monkeypatch) -> None:
    def fake_run(command, *, cwd, text, capture_output, check):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="modal auth failed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    try:
        execute_modal_rl_smoke(run_id="run_capsule_123", repo_root=tmp_path, output_dir=tmp_path)
    except RuntimeError as exc:
        assert "modal auth failed" in str(exc)
    else:
        raise AssertionError("Expected failed Modal command to raise RuntimeError")
