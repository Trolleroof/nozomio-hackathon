import json
import os
from pathlib import Path

from anygpu.crucible import signup_user
from anygpu.crucible_mcp import handle_tool_call
from anygpu.crucible_store import CrucibleStore


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
