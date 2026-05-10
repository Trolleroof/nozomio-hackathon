import json
from pathlib import Path

from anygpu.crucible import signup_user
from anygpu.crucible_mcp import handle_tool_call, list_tools
from anygpu.crucible_store import CrucibleStore


def _content(response: dict) -> dict:
    assert response["isError"] is False, response
    return response["content"]


def _setup_run(store: CrucibleStore) -> tuple[dict, dict]:
    admin = signup_user(store, "modal-agent@example.com", "pw", role="admin")
    contract = _content(
        handle_tool_call(
            store,
            "crucible_create_environment_contract",
            {
                "name": "line_world_ppo",
                "envSpec": {"runtime": "torch-vectorized", "max_steps": 16},
                "observationSchema": {"shape": [2], "dtype": "float32"},
                "actionSchema": {"type": "discrete", "n": 2},
                "rewardSpec": {"success_reward": 1.0, "step_penalty": -0.01},
                "passCriteria": {"min_success_rate": 0.9, "min_success_delta": 0.25},
            },
        )
    )
    capsule = _content(
        handle_tool_call(
            store,
            "crucible_request_gpu_run",
            {
                "userId": admin["id"],
                "prompt": "Run PPO on line-world on Modal T4.",
                "envContractId": contract["id"],
                "providerOffers": [{"provider": "modal", "gpu_name": "Tesla T4", "price_per_hr": 0.59, "available": True}],
                "costEstimate": {"estimated_cost_usd": 0.01, "estimated_runtime_minutes": 10},
                "sourceAgent": "mcp-test",
            },
        )
    )
    approval = _content(
        handle_tool_call(
            store,
            "crucible_approve_gpu_run",
            {
                "runId": capsule["id"],
                "approvedBy": admin["id"],
                "provider": "modal",
                "budgetUsd": 0.05,
                "maxRuntimeMinutes": 15,
                "teardownPolicy": {"terminate": "always", "maxIdleMinutes": 2},
            },
        )
    )
    return capsule, approval


def test_mcp_launch_gpu_run_can_execute_modal_and_publish_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()
    capsule, approval = _setup_run(store)

    def fake_execute_modal_rl_smoke(**kwargs):
        return {
            "result": {
                "device": "cuda",
                "gpu_name": "Tesla T4",
                "samples": 196608,
                "trained_policy_eval": {"success_rate": 1.0},
                "improvement": {"success_rate_delta": 1.0, "mean_return_delta": 1.25},
                "train": {"duration_sec": 7.0},
                "cost": {"estimated_gpu_cost_usd": 0.00115, "estimated_gpu_usd_per_hour": 0.59},
            },
            "audit": {"passed": True, "checks": {"ran_on_cuda": True}},
            "artifact": {
                "path": str(tmp_path / "modal.json"),
                "uri": "file://" + str(tmp_path / "modal.json"),
                "metadata": {
                    "passed": True,
                    "gpu_name": "Tesla T4",
                    "cost_usd": 0.00115,
                    "reward_delta": 1.25,
                    "success_rate_delta": 1.0,
                    "samples": 196608,
                    "duration_sec": 7.0,
                },
            },
            "training_event": {
                "phase": "train",
                "rollout_count": 3,
                "reward_mean": 1.25,
                "success_rate": 1.0,
                "cost_burn_usd": 0.00115,
                "gpu_name": "Tesla T4",
                "message": "Modal RL smoke passed on Tesla T4.",
            },
            "compute_memory": {
                "provider": "modal",
                "gpu_name": "Tesla T4",
                "event_type": "verified_training_run",
                "status": "passed",
                "summary": "Modal RL smoke passed on Tesla T4.",
                "pricing": {"price_per_hr": 0.59, "measured_cost_usd": 0.00115},
                "compatibility": {"algorithm": "ppo", "runtime": "torch-vectorized"},
            },
        }

    monkeypatch.setattr("anygpu.crucible_mcp.execute_modal_rl_smoke", fake_execute_modal_rl_smoke)

    launched = _content(
        handle_tool_call(
            store,
            "crucible_launch_gpu_run",
            {
                "runId": capsule["id"],
                "approvalToken": approval["token"],
                "execute": True,
                "executionMode": "modal",
                "gpu": "T4",
            },
        )
    )

    assert launched["status"] == "passed"
    assert launched["audit"]["passed"] is True
    assert launched["metrics"]["success_rate"] == 1.0
    assert launched["model_artifact_uri"].startswith("file://")
    assert any("Modal RL smoke passed" in entry["message"] for entry in launched["logs"])


def test_mcp_exposes_execution_feature_matrix(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()

    tool_names = {tool["name"] for tool in list_tools()}
    matrix = _content(handle_tool_call(store, "crucible_list_execution_features", {}))

    assert "crucible_list_execution_features" in tool_names
    by_id = {item["id"]: item for item in matrix["features"]}
    assert by_id["rl.modal_smoke"]["mcp_executable"] is True
    assert by_id["deployments.crucible_plan"]["mcp_executable"] is True
    assert by_id["deployments.crucible_plan"]["execution_mode"] == "simulated-safe"
    assert by_id["deployments.modal_vllm"]["mcp_tool"] == "deploy_cheapest"
    json.dumps(matrix)
