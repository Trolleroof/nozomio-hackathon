import importlib
import json
import sys
import types
from typing import Any, Callable


CORE_CRUCIBLE_TOOLS = [
    "crucible_plan_deployment",
    "crucible_approve_plan",
    "crucible_deploy_approved_plan",
    "crucible_get_deployment_status",
    "crucible_get_logs",
    "crucible_run_health_check",
    "crucible_stop_deployment",
]


def import_server_with_fake_fastmcp(monkeypatch):
    fastmcp_module = types.ModuleType("mcp.server.fastmcp")

    class FakeFastMCP:
        def __init__(self, name: str, **_kwargs: Any) -> None:
            self.name = name
            self.tools: dict[str, Callable[..., Any]] = {}
            self.settings = types.SimpleNamespace(
                host=None,
                port=None,
                stateless_http=None,
                json_response=None,
                transport_security=types.SimpleNamespace(allowed_hosts=[]),
            )

        def tool(self):
            def decorate(fn):
                self.tools[fn.__name__] = fn
                return fn

            return decorate

        def run(self, *_args: Any, **_kwargs: Any) -> None:
            pass

    fastmcp_module.FastMCP = FakeFastMCP
    monkeypatch.setitem(sys.modules, "mcp", types.ModuleType("mcp"))
    monkeypatch.setitem(sys.modules, "mcp.server", types.ModuleType("mcp.server"))
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_module)
    sys.modules.pop("mcp_server.server", None)
    return importlib.import_module("mcp_server.server")


def test_fastmcp_registers_core_crucible_deployment_tools(monkeypatch) -> None:
    server = import_server_with_fake_fastmcp(monkeypatch)

    assert set(CORE_CRUCIBLE_TOOLS) <= set(server.mcp.tools)


def test_fastmcp_core_crucible_tools_delegate_to_crucible_mcp(monkeypatch) -> None:
    server = import_server_with_fake_fastmcp(monkeypatch)
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_call(tool_name: str, arguments: dict[str, Any]) -> str:
        calls.append((tool_name, arguments))
        return json.dumps({"tool": tool_name, "arguments": arguments})

    monkeypatch.setattr(server, "_call_crucible_tool", fake_call)

    assert json.loads(
        server.crucible_plan_deployment(
            userId="user-1",
            prompt="Deploy Qwen cheaply",
            sourceAgent="agent",
            modelId="qwen-7b",
            objective="cheap",
        )
    )["tool"] == "crucible_plan_deployment"
    assert json.loads(server.crucible_approve_plan(planId="plan-1", userId="admin-1"))["tool"] == (
        "crucible_approve_plan"
    )
    assert json.loads(server.crucible_deploy_approved_plan(planId="plan-1", approvalToken="token-1"))["tool"] == (
        "crucible_deploy_approved_plan"
    )
    assert json.loads(server.crucible_get_deployment_status(deploymentId="dep-1"))["tool"] == (
        "crucible_get_deployment_status"
    )
    assert json.loads(server.crucible_get_logs(deploymentId="dep-1"))["tool"] == "crucible_get_logs"
    assert json.loads(server.crucible_run_health_check(deploymentId="dep-1"))["tool"] == (
        "crucible_run_health_check"
    )
    assert json.loads(server.crucible_stop_deployment(deploymentId="dep-1"))["tool"] == (
        "crucible_stop_deployment"
    )

    assert calls == [
        (
            "crucible_plan_deployment",
            {
                "userId": "user-1",
                "prompt": "Deploy Qwen cheaply",
                "sourceAgent": "agent",
                "modelId": "qwen-7b",
                "objective": "cheap",
            },
        ),
        ("crucible_approve_plan", {"planId": "plan-1", "userId": "admin-1"}),
        ("crucible_deploy_approved_plan", {"planId": "plan-1", "approvalToken": "token-1"}),
        ("crucible_get_deployment_status", {"deploymentId": "dep-1"}),
        ("crucible_get_logs", {"deploymentId": "dep-1"}),
        ("crucible_run_health_check", {"deploymentId": "dep-1"}),
        ("crucible_stop_deployment", {"deploymentId": "dep-1"}),
    ]
