import json
import os
import subprocess
import sys
from pathlib import Path

from anygpu.crucible import signup_user
from anygpu.crucible_mcp import handle_tool_call, list_tools
from anygpu.crucible_store import CrucibleStore

ROOT = Path(__file__).resolve().parents[1]


def test_mcp_plan_deploy_requires_approval_and_then_succeeds(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()
    user = signup_user(store, "agent@example.com", "pw", role="admin")

    plan_result = handle_tool_call(
        store,
        "crucible_plan_deployment",
        {"prompt": "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.", "sourceAgent": "hermes", "userId": user["id"]},
    )
    plan = plan_result["content"]
    assert plan["approval_required"] is True

    blocked = handle_tool_call(store, "crucible_deploy_approved_plan", {"planId": plan["id"]})
    assert blocked["isError"] is True
    assert blocked["content"]["error"] == "Approval required before launching GPU resources."

    approval = handle_tool_call(store, "crucible_approve_plan", {"planId": plan["id"], "userId": user["id"]})["content"]
    deployed = handle_tool_call(
        store,
        "crucible_deploy_approved_plan",
        {"planId": plan["id"], "approvalToken": approval["token"]},
    )["content"]
    assert deployed["status"] == "ready"

    status = handle_tool_call(store, "crucible_get_deployment_status", {"deploymentId": deployed["id"]})["content"]
    logs = handle_tool_call(store, "crucible_get_logs", {"deploymentId": deployed["id"]})["content"]
    health = handle_tool_call(store, "crucible_run_health_check", {"deploymentId": deployed["id"]})["content"]
    stopped = handle_tool_call(store, "crucible_stop_deployment", {"deploymentId": deployed["id"]})["content"]
    assert status["id"] == deployed["id"]
    assert logs[0]["message"]
    assert health["status"] == "ready"
    assert stopped["status"] == "stopped"


def test_mcp_plan_accepts_model_and_objective(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()
    user = signup_user(store, "agent-model@example.com", "pw", role="admin")

    plan = handle_tool_call(
        store,
        "crucible_plan_deployment",
        {
            "prompt": "Run Mistral where reliability wins.",
            "sourceAgent": "web",
            "userId": user["id"],
            "modelId": "mistralai/Mistral-7B-Instruct-v0.3",
            "objective": "reliable",
        },
    )["content"]

    assert plan["model_id"] == "mistralai/Mistral-7B-Instruct-v0.3"
    assert plan["objective"] == "reliable"


def test_mcp_context_and_failure_tools(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()

    context = handle_tool_call(store, "crucible_search_context", {"query": "Modal vLLM health"})["content"]
    failure = handle_tool_call(
        store,
        "crucible_explain_failure",
        {"deploymentId": "dep_failed", "error": "health check failed"},
    )["content"]

    assert context
    assert failure["context_used"]
    assert "health check failed" in failure["failure"]


def test_mcp_stdio_json_shape(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()
    response = handle_tool_call(store, "crucible_list_deployments", {})

    encoded = json.dumps(response)

    assert json.loads(encoded)["content"] == []


def test_mcp_exposes_provider_capabilities_tool(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()

    names = {tool["name"] for tool in list_tools()}
    response = handle_tool_call(store, "crucible_list_provider_capabilities", {})

    assert "crucible_list_provider_capabilities" in names
    assert response["isError"] is False
    assert {"Modal", "SkyPilot", "Lambda Cloud", "CoreWeave"} <= {item["provider"] for item in response["content"]}


def test_cli_mcp_call_runs_without_web_or_import_harness(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["ANYGPU_HOME"] = str(tmp_path / "state")
    env["PYTHONPATH"] = str(ROOT)

    user = json.loads(
        subprocess.run(
            [sys.executable, "-m", "anygpu", "crucible", "signup", "--email", "agent@example.com", "--password", "pw"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "anygpu",
            "crucible",
            "mcp-call",
            "crucible_plan_deployment",
            "--arguments-json",
            json.dumps({"userId": user["id"], "prompt": "Deploy Qwen 7B cheaply", "sourceAgent": "cli-agent"}),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["isError"] is False
    assert response["content"]["source"] == "cli-agent"
