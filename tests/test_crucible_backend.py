import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from anygpu.crucible import (
    ApprovalRequiredError,
    approve_plan,
    create_deployment_plan,
    deploy_approved_plan,
    get_deployment,
    get_deployment_logs,
    list_provider_capabilities,
    run_health_check,
    login_user,
    signup_user,
    stop_deployment,
)
from anygpu.crucible_store import CrucibleStore


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


def test_signup_login_and_sqlite_persistence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))

    store = CrucibleStore()
    user = signup_user(store, "judge@example.com", "correct horse battery staple")
    session = login_user(store, "judge@example.com", "correct horse battery staple")

    assert user["email"] == "judge@example.com"
    assert user["role"] == "user"
    assert session["token"].startswith("sess_")

    db_path = tmp_path / "state" / "crucible.sqlite3"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("select email, role from users").fetchall()
    assert rows == [("judge@example.com", "user")]


def test_plan_requires_approval_and_records_agent_context(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()
    user = signup_user(store, "judge@example.com", "pw")

    plan = create_deployment_plan(
        store,
        user["id"],
        "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
        source="agent",
    )

    assert plan["status"] == "generated"
    assert plan["model_id"] == "Qwen/Qwen2.5-7B-Instruct"
    assert plan["objective"] == "cheapest"
    assert plan["approval_required"] is True
    assert plan["recommendation"]["provider"] in {"Modal", "SkyPilot"}
    assert plan["context_used"]
    assert "approval" in plan["next_action"].lower()


def test_plan_accepts_web_model_and_objective(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()
    user = signup_user(store, "planner@example.com", "pw")

    plan = create_deployment_plan(
        store,
        user["id"],
        "Deploy Mistral with reliability first.",
        source="web",
        model_id="mistralai/Mistral-7B-Instruct-v0.3",
        objective="reliable",
    )

    assert plan["source"] == "web"
    assert plan["model_id"] == "mistralai/Mistral-7B-Instruct-v0.3"
    assert plan["objective"] == "reliable"
    assert "mistralai/Mistral-7B-Instruct-v0.3" in plan["context_used"][1]["fact"]


def test_web_bridge_creates_backend_plan_for_web_user(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["ANYGPU_HOME"] = str(tmp_path / "state")
    env["PYTHONPATH"] = str(ROOT)

    result = subprocess.run(
        [sys.executable, "-m", "anygpu.crucible_web_bridge"],
        cwd=ROOT,
        env=env,
        input=json.dumps(
            {
                "action": "plan",
                "userId": "web_user_123",
                "email": "web@example.com",
                "prompt": "Deploy Llama 8B reliably.",
                "modelId": "meta-llama/Meta-Llama-3.1-8B-Instruct",
                "objective": "reliable",
            }
        ),
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)

    assert payload["model_id"] == "meta-llama/Meta-Llama-3.1-8B-Instruct"
    assert payload["objective"] == "reliable"
    assert payload["user_id"] == "web_user_123"


def test_web_bridge_deploys_existing_backend_plan(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["ANYGPU_HOME"] = str(tmp_path / "state")
    env["PYTHONPATH"] = str(ROOT)

    plan_result = subprocess.run(
        [sys.executable, "-m", "anygpu.crucible_web_bridge"],
        cwd=ROOT,
        env=env,
        input=json.dumps(
            {
                "action": "plan",
                "userId": "web_user_123",
                "prompt": "Deploy Qwen 7B cheaply.",
                "modelId": "Qwen/Qwen2.5-7B-Instruct",
                "objective": "cheapest",
            }
        ),
        text=True,
        capture_output=True,
        check=True,
    )
    plan = json.loads(plan_result.stdout)

    deploy_result = subprocess.run(
        [sys.executable, "-m", "anygpu.crucible_web_bridge"],
        cwd=ROOT,
        env=env,
        input=json.dumps({"action": "deploy", "planId": plan["id"]}),
        text=True,
        capture_output=True,
        check=True,
    )
    deployment = json.loads(deploy_result.stdout)

    assert deployment["plan_id"] == plan["id"]
    assert deployment["status"] == "ready"
    assert deployment["endpoint_url"].endswith("/v1/chat/completions")
    assert deployment["approval"]["token"].startswith("approval_token_")


def test_deploy_is_blocked_until_approved_then_records_health_logs_benchmark_stop(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    store = CrucibleStore()
    admin = signup_user(store, "admin@example.com", "pw", role="admin")
    plan = create_deployment_plan(store, admin["id"], "Deploy Qwen 7B cheaply", source="cli")

    try:
        deploy_approved_plan(store, plan["id"])
    except ApprovalRequiredError as exc:
        assert str(exc) == "Approval required before launching GPU resources."
    else:
        raise AssertionError("deployment should be blocked without approval")

    approval = approve_plan(store, plan["id"], admin["id"])
    deployment = deploy_approved_plan(store, plan["id"], approval_token=approval["token"])

    assert deployment["status"] == "ready"
    assert deployment["endpoint_url"].endswith("/v1/chat/completions")
    assert deployment["health_checks"][0]["status"] == "passing"
    assert deployment["benchmark"]["tokens_per_second"] > 0
    assert any("Health checks passed" in log["message"] for log in deployment["logs"])

    stopped = get_deployment(store, deployment["id"])
    assert stopped["status"] == "ready"

    health = run_health_check(store, deployment["id"])
    logs = get_deployment_logs(store, deployment["id"])
    stopped = stop_deployment(store, deployment["id"])

    assert health["status"] == "ready"
    assert any("Health checks passed" in log["message"] for log in logs)
    assert stopped["status"] == "stopped"
    assert get_deployment(store, deployment["id"])["status"] == "stopped"


def test_provider_capabilities_are_honest_without_credentials(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("SKYPILOT_API_SERVER_ENDPOINT", raising=False)
    monkeypatch.delenv("VAST_AI_API_KEY", raising=False)
    monkeypatch.delenv("ANYGPU_VAST_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    store = CrucibleStore()

    capabilities = list_provider_capabilities(store)

    by_provider = {item["provider"]: item for item in capabilities}
    assert by_provider["Modal"]["supports_openai_endpoint"] is True
    assert by_provider["Modal"]["supports_deploy"] is False
    assert by_provider["SkyPilot"]["supports_deploy"] is False
    assert by_provider["Lambda Cloud"]["status"] in {"configured", "unsupported"}
    assert by_provider["CoreWeave"]["status"] in {"configured", "unsupported"}
    assert by_provider["Vast.ai"]["status"] == "unsupported"
    assert by_provider["Vast.ai"]["supports_openai_endpoint"] is True


def test_provider_capabilities_configures_vast_with_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("VAST_AI_API_KEY", "test-token")
    store = CrucibleStore()

    capabilities = list_provider_capabilities(store)

    vast = {item["provider"]: item for item in capabilities}["Vast.ai"]
    assert vast["status"] == "configured"
    assert vast["supports_deploy"] is True
    assert vast["supports_openai_endpoint"] is True
    assert vast["credentials_required"] == ["VAST_AI_API_KEY", "ANYGPU_VAST_API_KEY"]


def test_provider_capabilities_configures_vast_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("VAST_AI_API_KEY", raising=False)
    monkeypatch.delenv("ANYGPU_VAST_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("VAST_AI_API_KEY=dotenv-token\n")
    store = CrucibleStore()

    capabilities = list_provider_capabilities(store)

    vast = {item["provider"]: item for item in capabilities}["Vast.ai"]
    assert vast["status"] == "configured"
    assert vast["supports_deploy"] is True


def test_crucible_cli_plan_approve_deploy_status(tmp_path: Path) -> None:
    home = tmp_path / "state"
    signup = json.loads(run_cli(home, "crucible", "signup", "--email", "admin@example.com", "--password", "pw", "--role", "admin"))
    assert signup["role"] == "admin"

    plan = json.loads(
        run_cli(home, "crucible", "plan", "--user-id", signup["id"], "--prompt", "Deploy Qwen 7B cheaply")
    )
    blocked = json.loads(run_cli(home, "crucible", "deploy", "--plan-id", plan["id"]))
    assert blocked["error"] == "Approval required before launching GPU resources."

    approval = json.loads(run_cli(home, "crucible", "approve", "--plan-id", plan["id"], "--user-id", signup["id"]))
    deployment = json.loads(run_cli(home, "crucible", "deploy", "--plan-id", plan["id"], "--approval-token", approval["token"]))
    status = json.loads(run_cli(home, "crucible", "status", "--deployment-id", deployment["id"]))
    logs = json.loads(run_cli(home, "crucible", "logs", "--deployment-id", deployment["id"]))
    health = json.loads(run_cli(home, "crucible", "health", "--deployment-id", deployment["id"]))
    stopped = json.loads(run_cli(home, "crucible", "stop", "--deployment-id", deployment["id"]))

    assert status["status"] == "ready"
    assert logs[0]["message"]
    assert health["status"] == "ready"
    assert stopped["status"] == "stopped"


def test_crucible_cli_exposes_only_backend_agent_commands(tmp_path: Path) -> None:
    help_output = run_cli(tmp_path / "state", "crucible", "--help")

    for command in [
        "signup",
        "plan",
        "approve",
        "deploy",
        "status",
        "logs",
        "health",
        "stop",
        "providers",
        "mcp-tools",
        "mcp-call",
    ]:
        assert command in help_output
    assert "web" not in help_output
