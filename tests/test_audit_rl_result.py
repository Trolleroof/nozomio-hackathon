from experiments.audit_rl_result import audit_result


def result_payload(*, device: str = "cuda", gpu_name: str | None = "NVIDIA T4", success_delta: float = 1.0) -> dict:
    return {
        "device": device,
        "gpu_name": gpu_name,
        "samples": 262144,
        "initial_policy_eval": {"success_rate": 0.0},
        "trained_policy_eval": {"success_rate": success_delta},
        "improvement": {"success_rate_delta": success_delta, "mean_return_delta": 1.0},
        "train": {"duration_sec": 3.0},
        "cost": {"estimated_gpu_cost_usd": 0.001},
    }


def test_audit_accepts_cuda_artifact_with_learning_improvement() -> None:
    audit = audit_result(result_payload())

    assert audit["passed"] is True
    assert audit["checks"]["ran_on_cuda"] is True
    assert audit["summary"]["gpu_name"] == "NVIDIA T4"


def test_audit_rejects_cpu_artifact_even_when_policy_improves() -> None:
    audit = audit_result(result_payload(device="cpu", gpu_name=None))

    assert audit["passed"] is False
    assert audit["checks"]["ran_on_cuda"] is False
    assert audit["checks"]["mean_return_improved"] is True


def test_audit_rejects_cuda_artifact_without_enough_success_improvement() -> None:
    audit = audit_result(result_payload(success_delta=0.1))

    assert audit["passed"] is False
    assert audit["checks"]["ran_on_cuda"] is True
    assert audit["checks"]["success_rate_improved"] is False
