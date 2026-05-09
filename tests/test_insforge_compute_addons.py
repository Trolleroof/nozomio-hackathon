from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from anygpu.crucible import signup_user
from anygpu.crucible_store import CrucibleStore


def test_insforge_run_capsule_requires_signed_approval_before_launch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))

    from anygpu.insforge_compute import (
        ApprovalRequiredError,
        approve_gpu_run,
        create_environment_contract,
        launch_gpu_run,
        request_gpu_run,
    )

    store = CrucibleStore()
    admin = signup_user(store, "admin@example.com", "pw", role="admin")
    contract = create_environment_contract(
        store,
        name="line_world_ppo",
        env_spec={"runtime": "torch-vectorized", "max_steps": 32},
        observation_schema={"shape": [2], "dtype": "float32"},
        action_schema={"type": "discrete", "n": 2},
        reward_spec={"success_reward": 1.0, "step_penalty": -0.01},
        pass_criteria={"min_success_rate": 0.9, "min_success_delta": 0.25},
        branch_name="rl-line-world",
    )
    capsule = request_gpu_run(
        store,
        user_id=admin["id"],
        prompt="Train PPO on the line-world environment using the cheapest verified GPU.",
        env_contract_id=contract["id"],
        provider_offers=[
            {"provider": "modal", "gpu_name": "Tesla T4", "price_per_hr": 0.59, "available": True},
            {"provider": "vast", "gpu_name": "Tesla V100", "price_per_hr": 0.0209, "available": True},
        ],
        cost_estimate={"estimated_cost_usd": 0.01, "estimated_runtime_minutes": 10},
        source_agent="codex",
    )

    assert capsule["status"] == "approval_required"
    assert capsule["approval_token"] is None
    assert capsule["provider_offers"][0]["provider"] == "vast"

    try:
        launch_gpu_run(store, capsule["id"])
    except ApprovalRequiredError as exc:
        assert "signed approval" in str(exc)
    else:
        raise AssertionError("paid GPU run should not launch without a signed approval row")

    approval = approve_gpu_run(
        store,
        run_id=capsule["id"],
        approved_by=admin["id"],
        provider="modal",
        budget_usd=0.05,
        max_runtime_minutes=15,
        teardown_policy={"after_status": ["passed", "failed"], "max_idle_minutes": 2},
    )
    launched = launch_gpu_run(store, capsule["id"], approval_token=approval["token"])

    assert approval["status"] == "signed"
    assert approval["budget_usd"] == 0.05
    assert launched["status"] == "running"
    assert launched["provider"] == "modal"
    assert launched["approval_token"] == approval["token"]


def test_insforge_live_memory_events_artifacts_and_next_run_recommendation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))

    from anygpu.insforge_compute import (
        approve_gpu_run,
        create_environment_contract,
        launch_gpu_run,
        publish_run_artifact,
        recommend_next_gpu_run,
        record_compute_memory,
        record_training_event,
        request_gpu_run,
    )

    store = CrucibleStore()
    admin = signup_user(store, "admin@example.com", "pw", role="admin")
    contract = create_environment_contract(
        store,
        name="line_world_ppo",
        env_spec={"runtime": "torch-vectorized"},
        observation_schema={"shape": [2]},
        action_schema={"type": "discrete", "n": 2},
        reward_spec={"success_reward": 1.0},
        pass_criteria={"min_success_rate": 0.9, "min_success_delta": 0.25},
    )
    capsule = request_gpu_run(
        store,
        user_id=admin["id"],
        prompt="Run a cheap Modal T4 PPO smoke.",
        env_contract_id=contract["id"],
        provider_offers=[{"provider": "modal", "gpu_name": "Tesla T4", "price_per_hr": 0.59, "available": True}],
        cost_estimate={"estimated_cost_usd": 0.0007},
    )
    approval = approve_gpu_run(
        store,
        run_id=capsule["id"],
        approved_by=admin["id"],
        provider="modal",
        budget_usd=0.05,
        max_runtime_minutes=10,
        teardown_policy={"terminate": "always"},
    )
    launch_gpu_run(store, capsule["id"], approval_token=approval["token"])

    event = record_training_event(
        store,
        run_id=capsule["id"],
        phase="train",
        rollout_count=3,
        reward_mean=1.2,
        success_rate=1.0,
        cost_burn_usd=0.00065,
        gpu_name="Tesla T4",
        message="PPO update 3 passed target success rate.",
    )
    memory = record_compute_memory(
        store,
        run_id=capsule["id"],
        provider="modal",
        gpu_name="Tesla T4",
        event_type="verified_training_run",
        status="passed",
        summary="Modal T4 improved line-world PPO from zero success to 1.0 success.",
        pricing={"price_per_hr": 0.59, "measured_cost_usd": 0.00065},
        compatibility={"env_contract_id": contract["id"], "algorithm": "ppo"},
    )
    artifact = publish_run_artifact(
        store,
        run_id=capsule["id"],
        kind="metrics_json",
        uri="insforge://storage/rl-runs/modal_t4_line_world.json",
        metadata={
            "passed": True,
            "gpu_name": "Tesla T4",
            "cost_usd": 0.00065,
            "reward_delta": 1.25,
            "success_rate_delta": 0.9999,
        },
    )
    recommendation = recommend_next_gpu_run(store, env_contract_id=contract["id"])

    assert event["channel"] == f"training:{capsule['id']}"
    assert memory["status"] == "passed"
    assert artifact["passed"] is True
    assert artifact["success_rate_delta"] == 0.9999
    assert recommendation["recommended_provider"] == "modal"
    assert recommendation["evidence"][0]["run_id"] == capsule["id"]


def test_insforge_experiment_branches_are_isolated_until_merged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))

    from anygpu.insforge_compute import create_experiment_branch, create_environment_contract, merge_experiment_branch

    store = CrucibleStore()
    branch = create_experiment_branch(
        store,
        name="reward-shaping-v2",
        parent_branch="main",
        schema_snapshot={"tables": ["rl_environment_contracts", "rl_run_capsules"]},
    )
    contract = create_environment_contract(
        store,
        name="line_world_reward_shaping",
        env_spec={"runtime": "torch-vectorized", "reward_variant": "dense"},
        observation_schema={"shape": [2]},
        action_schema={"type": "discrete", "n": 2},
        reward_spec={"success_reward": 1.0, "dense_distance_reward": 0.05},
        pass_criteria={"min_success_rate": 0.95},
        branch_name=branch["name"],
    )
    merged = merge_experiment_branch(store, branch["name"], merge_note="Dense reward contract validated.")

    assert branch["status"] == "active"
    assert contract["branch_name"] == "reward-shaping-v2"
    assert merged["status"] == "merged"
    assert merged["merge_note"] == "Dense reward contract validated."


def test_insforge_schema_migration_contains_function_safety_gates() -> None:
    migration = Path("insforge/migrations/0001_rl_compute_control_plane.sql").read_text()

    for table in [
        "rl_run_capsules",
        "rl_compute_approvals",
        "rl_compute_memory",
        "rl_experiment_branches",
        "rl_training_events",
        "rl_environment_contracts",
        "rl_run_artifacts",
    ]:
        assert f"create table if not exists public.{table}" in migration.lower()

    for function_name in [
        "request_gpu_run",
        "approve_run",
        "mark_teardown_verified",
        "publish_result",
        "recommend_next_gpu_run",
    ]:
        assert function_name in migration


def test_insforge_mcp_tools_expose_run_capsules_and_next_run() -> None:
    from anygpu.crucible_mcp import list_tools

    tool_names = {tool["name"] for tool in list_tools()}

    assert "crucible_request_gpu_run" in tool_names
    assert "crucible_approve_gpu_run" in tool_names
    assert "crucible_publish_run_artifact" in tool_names
    assert "crucible_recommend_next_gpu_run" in tool_names
