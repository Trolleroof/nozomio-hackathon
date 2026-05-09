from __future__ import annotations

import json
import os
import sqlite3
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


def mcp_call(home: Path, tool: str, arguments: dict) -> dict:
    return json.loads(
        run_cli(
            home,
            "crucible",
            "mcp-call",
            tool,
            "--arguments-json",
            json.dumps(arguments),
        )
    )


def mcp_content(home: Path, tool: str, arguments: dict) -> dict:
    response = mcp_call(home, tool, arguments)
    assert response["isError"] is False, response
    return response["content"]


def test_cli_mcp_live_flow_covers_all_insforge_rl_gpu_addons(tmp_path: Path) -> None:
    home = tmp_path / "state"
    tools = json.loads(run_cli(home, "crucible", "mcp-tools"))
    tool_names = {tool["name"] for tool in tools}

    for tool_name in {
        "crucible_create_experiment_branch",
        "crucible_merge_experiment_branch",
        "crucible_create_environment_contract",
        "crucible_request_gpu_run",
        "crucible_list_run_capsules",
        "crucible_approve_gpu_run",
        "crucible_launch_gpu_run",
        "crucible_record_training_event",
        "crucible_record_compute_memory",
        "crucible_publish_run_artifact",
        "crucible_recommend_next_gpu_run",
    }:
        assert tool_name in tool_names

    admin = json.loads(
        run_cli(
            home,
            "crucible",
            "signup",
            "--email",
            "admin@example.com",
            "--password",
            "pw",
            "--role",
            "admin",
        )
    )
    branch = mcp_content(
        home,
        "crucible_create_experiment_branch",
        {
            "name": "live-line-world",
            "parentBranch": "main",
            "schemaSnapshot": {"tables": ["rl_run_capsules", "rl_environment_contracts"]},
        },
    )
    contract = mcp_content(
        home,
        "crucible_create_environment_contract",
        {
            "name": "line_world_ppo",
            "branchName": branch["name"],
            "envSpec": {"runtime": "torch-vectorized", "max_steps": 32},
            "observationSchema": {"shape": [2], "dtype": "float32"},
            "actionSchema": {"type": "discrete", "n": 2},
            "rewardSpec": {"success_reward": 1.0, "step_penalty": -0.01},
            "passCriteria": {"min_success_rate": 0.9, "min_success_delta": 0.25},
        },
    )
    capsule = mcp_content(
        home,
        "crucible_request_gpu_run",
        {
            "userId": admin["id"],
            "prompt": "Run PPO on line-world with the cheapest verified GPU.",
            "envContractId": contract["id"],
            "providerOffers": [
                {"provider": "modal", "gpu_name": "Tesla T4", "price_per_hr": 0.59, "available": True},
                {"provider": "vast", "gpu_name": "Tesla V100", "price_per_hr": 0.0209, "available": True},
            ],
            "costEstimate": {"estimated_cost_usd": 0.01, "estimated_runtime_minutes": 10},
            "sourceAgent": "codex-live-test",
        },
    )

    blocked = mcp_call(home, "crucible_launch_gpu_run", {"runId": capsule["id"], "approvalToken": "missing"})
    assert blocked["isError"] is True
    assert "signed approval" in blocked["content"]["error"]

    approval = mcp_content(
        home,
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
    launched = mcp_content(
        home,
        "crucible_launch_gpu_run",
        {"runId": capsule["id"], "approvalToken": approval["token"]},
    )
    event = mcp_content(
        home,
        "crucible_record_training_event",
        {
            "runId": capsule["id"],
            "phase": "train",
            "rolloutCount": 3,
            "rewardMean": 1.2,
            "successRate": 1.0,
            "costBurnUsd": 0.00065,
            "gpuName": "Tesla T4",
            "message": "live MCP flow recorded PPO success",
        },
    )
    memory = mcp_content(
        home,
        "crucible_record_compute_memory",
        {
            "runId": capsule["id"],
            "provider": "modal",
            "gpuName": "Tesla T4",
            "eventType": "verified_training_run",
            "status": "passed",
            "summary": "Modal T4 passed the line-world PPO smoke run.",
            "pricing": {"price_per_hr": 0.59, "measured_cost_usd": 0.00065},
            "compatibility": {"envContractId": contract["id"], "algorithm": "ppo"},
        },
    )
    artifact = mcp_content(
        home,
        "crucible_publish_run_artifact",
        {
            "runId": capsule["id"],
            "kind": "metrics_json",
            "uri": "insforge://storage/rl-runs/live-modal-t4.json",
            "metadata": {
                "passed": True,
                "gpu_name": "Tesla T4",
                "cost_usd": 0.00065,
                "reward_delta": 1.25,
                "success_rate_delta": 0.9999,
            },
        },
    )
    listed = mcp_content(home, "crucible_list_run_capsules", {})
    recommendation = mcp_content(home, "crucible_recommend_next_gpu_run", {"envContractId": contract["id"]})
    merged = mcp_content(
        home,
        "crucible_merge_experiment_branch",
        {"name": branch["name"], "mergeNote": "Live MCP flow validated all InsForge add-ons."},
    )

    assert launched["status"] == "running"
    assert event["channel"] == f"training:{capsule['id']}"
    assert memory["status"] == "passed"
    assert artifact["passed"] is True
    assert listed[0]["id"] == capsule["id"]
    assert recommendation["recommended_provider"] == "modal"
    assert recommendation["evidence"][0]["run_id"] == capsule["id"]
    assert merged["status"] == "merged"

    with sqlite3.connect(home / "crucible.sqlite3") as conn:
        counts = {
            table: conn.execute(f"select count(*) from {table}").fetchone()[0]
            for table in [
                "rl_experiment_branches",
                "rl_environment_contracts",
                "rl_run_capsules",
                "rl_compute_approvals",
                "rl_training_events",
                "rl_compute_memory",
                "rl_run_artifacts",
            ]
        }

    assert counts == {
        "rl_experiment_branches": 1,
        "rl_environment_contracts": 1,
        "rl_run_capsules": 1,
        "rl_compute_approvals": 1,
        "rl_training_events": 1,
        "rl_compute_memory": 1,
        "rl_run_artifacts": 1,
    }
