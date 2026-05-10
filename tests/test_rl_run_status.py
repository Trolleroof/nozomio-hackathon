import json
from pathlib import Path

from experiments.rl_run_status import summarize_status


def write_artifact(path: Path, *, device: str, gpu_name: str | None) -> None:
    path.write_text(
        json.dumps(
            {
                "device": device,
                "gpu_name": gpu_name,
                "samples": 6144,
                "initial_policy_eval": {"success_rate": 0.0},
                "trained_policy_eval": {"success_rate": 1.0},
                "improvement": {"success_rate_delta": 1.0, "mean_return_delta": 1.25},
                "train": {"duration_sec": 0.5},
                "cost": {"estimated_gpu_cost_usd": 0.001},
            }
        )
    )


def provider_status() -> dict:
    return {
        "modal": {"cli_profile": {"available": True, "stdout": "test-profile"}, "token_env_present": False},
        "skypilot": {"api_server": {"available": True, "endpoint": "http://127.0.0.1:8080"}},
    }


def test_status_reports_incomplete_when_only_cpu_learning_artifact_exists(tmp_path: Path) -> None:
    write_artifact(tmp_path / "local.json", device="cpu", gpu_name=None)

    status = summarize_status(tmp_path, provider_status=provider_status())

    assert status["complete"] is False
    assert status["missing"] == ["No artifact currently passes CUDA/GPU completion audit."]
    artifact = status["artifacts"][0]
    assert artifact["learning_signal"]["passed"] is True
    assert artifact["gpu_completion"]["passed"] is False
    assert artifact["gpu_completion"]["checks"]["ran_on_cuda"] is False


def test_status_reports_complete_when_cuda_artifact_passes_audit(tmp_path: Path) -> None:
    write_artifact(tmp_path / "modal.json", device="cuda", gpu_name="NVIDIA T4")

    status = summarize_status(tmp_path, provider_status=provider_status())

    assert status["complete"] is True
    assert status["missing"] == []
    artifact = status["artifacts"][0]
    assert artifact["gpu_completion"]["passed"] is True
    assert artifact["gpu_completion"]["summary"]["gpu_name"] == "NVIDIA T4"


def test_status_skips_non_rl_json_artifacts(tmp_path: Path) -> None:
    (tmp_path / "provider_price_check.json").write_text('{"top_offers": [], "offer_count": 0}')
    write_artifact(tmp_path / "modal.json", device="cuda", gpu_name="NVIDIA T4")

    status = summarize_status(tmp_path, provider_status=provider_status())

    assert status["complete"] is True
    assert [artifact["path"] for artifact in status["artifacts"]] == [str(tmp_path / "modal.json")]
