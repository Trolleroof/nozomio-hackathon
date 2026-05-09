from __future__ import annotations

from typing import Any, Callable

from .crucible import (
    ApprovalRequiredError,
    approve_plan,
    create_deployment_plan,
    deploy_approved_plan,
    get_deployment,
    list_provider_capabilities,
    run_health_check,
    stop_deployment,
)


JSON = dict[str, Any]

TOOLS: list[JSON] = [
    {
        "name": "crucible_plan_deployment",
        "description": "Create a GPU deployment plan from a natural-language request.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "userId": {"type": "string"},
                "prompt": {"type": "string"},
                "sourceAgent": {"type": "string"},
            },
            "required": ["userId", "prompt"],
        },
    },
    {
        "name": "crucible_approve_plan",
        "description": "Record explicit human/admin approval before launching GPU resources.",
        "inputSchema": {
            "type": "object",
            "properties": {"planId": {"type": "string"}, "userId": {"type": "string"}},
            "required": ["planId", "userId"],
        },
    },
    {
        "name": "crucible_deploy_approved_plan",
        "description": "Deploy an approved plan, enforcing the approval token gate.",
        "inputSchema": {
            "type": "object",
            "properties": {"planId": {"type": "string"}, "approvalToken": {"type": "string"}},
            "required": ["planId"],
        },
    },
    {
        "name": "crucible_get_deployment_status",
        "description": "Fetch deployment status and endpoint metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {"deploymentId": {"type": "string"}},
            "required": ["deploymentId"],
        },
    },
    {
        "name": "crucible_get_logs",
        "description": "Fetch deployment lifecycle logs.",
        "inputSchema": {
            "type": "object",
            "properties": {"deploymentId": {"type": "string"}},
            "required": ["deploymentId"],
        },
    },
    {
        "name": "crucible_run_health_check",
        "description": "Run the stored deployment health-check workflow.",
        "inputSchema": {
            "type": "object",
            "properties": {"deploymentId": {"type": "string"}},
            "required": ["deploymentId"],
        },
    },
    {
        "name": "crucible_stop_deployment",
        "description": "Stop a deployment record and append stop logs.",
        "inputSchema": {
            "type": "object",
            "properties": {"deploymentId": {"type": "string"}},
            "required": ["deploymentId"],
        },
    },
    {
        "name": "crucible_list_deployments",
        "description": "List known Crucible deployments.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "crucible_list_provider_capabilities",
        "description": "List provider launch capability and credential status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "crucible_search_context",
        "description": "Search context snippets used by agent deployment decisions.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "crucible_explain_failure",
        "description": "Explain a deployment failure with relevant context snippets.",
        "inputSchema": {
            "type": "object",
            "properties": {"deploymentId": {"type": "string"}, "error": {"type": "string"}},
            "required": ["deploymentId", "error"],
        },
    },
]


def list_tools() -> list[JSON]:
    return [dict(tool) for tool in TOOLS]


def _ok(content: Any) -> JSON:
    return {"content": content, "isError": False}


def _error(message: str) -> JSON:
    return {"content": {"error": message}, "isError": True}


def _require(arguments: JSON, key: str) -> Any:
    value = arguments.get(key)
    if value is None or value == "":
        raise ValueError(f"Missing required argument: {key}")
    return value


def _optional_import(name: str) -> Callable[..., Any] | None:
    import anygpu.crucible as crucible

    value = getattr(crucible, name, None)
    return value if callable(value) else None


def _list_deployments(store: Any) -> list[JSON]:
    list_deployments = _optional_import("list_deployments")
    if list_deployments:
        return list_deployments(store)
    if hasattr(store, "list_deployments"):
        return store.list_deployments()
    return []


def _deployment_logs(store: Any, deployment_id: str) -> list[JSON]:
    get_logs = _optional_import("get_deployment_logs")
    if get_logs:
        return get_logs(store, deployment_id)
    deployment = get_deployment(store, deployment_id)
    return deployment.get("logs", [])


def _search_context(store: Any, query: str) -> list[JSON]:
    search_context = _optional_import("search_context")
    if search_context:
        return search_context(store, query)
    return [
        {
            "title": "Modal vLLM deployment health",
            "source": "crucible",
            "snippet": "Check OpenAI-compatible health endpoints before routing traffic to a vLLM deployment.",
        },
        {
            "title": "Approval gate",
            "source": "crucible",
            "snippet": "GPU launches require explicit approval before provider resources are created.",
        },
    ]


def _explain_failure(store: Any, deployment_id: str, error: str) -> JSON:
    explain_failure = _optional_import("explain_failure")
    if explain_failure:
        return explain_failure(store, deployment_id, error)
    context = _search_context(store, error)
    return {
        "deployment_id": deployment_id,
        "failure": error,
        "context_used": context,
        "likely_cause": "The deployment did not pass its provider or runtime health check.",
        "next_action": "Inspect deployment logs, verify endpoint health, and redeploy after approval if needed.",
    }


def handle_tool_call(store: Any, tool_name: str, arguments: JSON | None = None) -> JSON:
    arguments = arguments or {}
    try:
        if tool_name == "crucible_plan_deployment":
            plan = create_deployment_plan(
                store,
                _require(arguments, "userId"),
                _require(arguments, "prompt"),
                source=arguments.get("sourceAgent") or "mcp",
            )
            return _ok(plan)
        if tool_name == "crucible_approve_plan":
            approval = approve_plan(store, _require(arguments, "planId"), _require(arguments, "userId"))
            return _ok(approval)
        if tool_name == "crucible_deploy_approved_plan":
            deployment = deploy_approved_plan(
                store,
                _require(arguments, "planId"),
                approval_token=arguments.get("approvalToken"),
            )
            return _ok(deployment)
        if tool_name == "crucible_get_deployment_status":
            return _ok(get_deployment(store, _require(arguments, "deploymentId")))
        if tool_name == "crucible_get_logs":
            return _ok(_deployment_logs(store, _require(arguments, "deploymentId")))
        if tool_name == "crucible_run_health_check":
            return _ok(run_health_check(store, _require(arguments, "deploymentId")))
        if tool_name == "crucible_stop_deployment":
            return _ok(stop_deployment(store, _require(arguments, "deploymentId")))
        if tool_name == "crucible_list_deployments":
            return _ok(_list_deployments(store))
        if tool_name == "crucible_list_provider_capabilities":
            return _ok(list_provider_capabilities(store))
        if tool_name == "crucible_search_context":
            return _ok(_search_context(store, _require(arguments, "query")))
        if tool_name == "crucible_explain_failure":
            return _ok(
                _explain_failure(
                    store,
                    _require(arguments, "deploymentId"),
                    _require(arguments, "error"),
                )
            )
        return _error(f"Unknown Crucible MCP tool: {tool_name}")
    except ApprovalRequiredError as exc:
        return _error(str(exc))
    except ValueError as exc:
        return _error(str(exc))
