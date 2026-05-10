from experiments.audit_rl_result import audit_result
from experiments.modal_rl_smoke import run_local_smoke


def test_local_rl_smoke_policy_improves_on_vector_env() -> None:
    result = run_local_smoke(updates=3, n_envs=128, rollout_steps=16)

    assert result["initial_policy_eval"]["success_rate"] == 0.0
    assert result["trained_policy_eval"]["success_rate"] >= 0.90
    assert result["improvement"]["mean_return_delta"] > 0
    assert result["device"] == "cpu"
    assert result["passed"] is False


def test_rl_result_audit_requires_gpu_for_completion() -> None:
    result = run_local_smoke(updates=3, n_envs=128, rollout_steps=16)

    cpu_audit = audit_result(result, require_cuda=False)
    gpu_audit = audit_result(result, require_cuda=True)

    assert cpu_audit["passed"] is True
    assert gpu_audit["passed"] is False
    assert gpu_audit["checks"]["ran_on_cuda"] is False
