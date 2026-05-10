from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable

from .modal_rl_executor import execute_modal_rl_smoke
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
from .insforge_compute import (
    ApprovalRequiredError as InsForgeApprovalRequiredError,
    approve_gpu_run,
    create_experiment_branch,
    create_environment_contract,
    get_run_capsule,
    launch_gpu_run,
    list_run_capsules,
    merge_experiment_branch,
    publish_run_artifact,
    recommend_next_gpu_run,
    record_compute_memory,
    record_training_event,
    request_gpu_run,
)
from .public_mcp_access import (
    claim_public_mcp_credit,
    consume_public_mcp_credit,
    public_mcp_credit_status,
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
                "modelId": {"type": "string"},
                "objective": {"type": "string"},
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
    {
        "name": "crucible_create_experiment_branch",
        "description": "Create an isolated InsForge-style experiment branch for RL environment or workflow changes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "parentBranch": {"type": "string"},
                "schemaSnapshot": {"type": "object"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "crucible_merge_experiment_branch",
        "description": "Mark an experiment branch as merged after its schema or environment contract changes are validated.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "mergeNote": {"type": "string"},
            },
            "required": ["name", "mergeNote"],
        },
    },
    {
        "name": "crucible_create_environment_contract",
        "description": "Create an agent-readable RL environment contract with observation, action, reward, and pass criteria schemas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "envSpec": {"type": "object"},
                "observationSchema": {"type": "object"},
                "actionSchema": {"type": "object"},
                "rewardSpec": {"type": "object"},
                "passCriteria": {"type": "object"},
                "branchName": {"type": "string"},
            },
            "required": ["name", "envSpec", "observationSchema", "actionSchema", "rewardSpec", "passCriteria"],
        },
    },
    {
        "name": "crucible_request_gpu_run",
        "description": "Create a durable InsForge-style RL/GPU run capsule that cannot launch until approved.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "userId": {"type": "string"},
                "prompt": {"type": "string"},
                "envContractId": {"type": "string"},
                "providerOffers": {"type": "array", "items": {"type": "object"}},
                "costEstimate": {"type": "object"},
                "sourceAgent": {"type": "string"},
            },
            "required": ["userId", "prompt", "envContractId", "providerOffers", "costEstimate"],
        },
    },
    {
        "name": "crucible_list_run_capsules",
        "description": "List durable InsForge-style RL/GPU run capsules for agent planning.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "crucible_approve_gpu_run",
        "description": "Create the signed approval ledger row required before a paid RL/GPU run launches.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "runId": {"type": "string"},
                "approvedBy": {"type": "string"},
                "provider": {"type": "string"},
                "budgetUsd": {"type": "number"},
                "maxRuntimeMinutes": {"type": "integer"},
                "teardownPolicy": {"type": "object"},
            },
            "required": ["runId", "approvedBy", "provider", "budgetUsd", "maxRuntimeMinutes", "teardownPolicy"],
        },
    },
    {
        "name": "crucible_launch_gpu_run",
        "description": "Launch an RL/GPU run capsule after validating its signed approval token; optionally execute the Modal RL smoke.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "runId": {"type": "string"},
                "approvalToken": {"type": "string"},
                "execute": {"type": "boolean"},
                "executionMode": {"type": "string", "enum": ["record", "modal"]},
                "gpu": {"type": "string"},
                "updates": {"type": "integer"},
                "nEnvs": {"type": "integer"},
                "rolloutSteps": {"type": "integer"},
                "ppoEpochs": {"type": "integer"},
                "minibatchSize": {"type": "integer"},
            },
            "required": ["runId", "approvalToken"],
        },
    },
    {
        "name": "crucible_record_training_event",
        "description": "Append realtime-style training progress for an RL/GPU run capsule.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "runId": {"type": "string"},
                "phase": {"type": "string"},
                "rolloutCount": {"type": "integer"},
                "rewardMean": {"type": "number"},
                "successRate": {"type": "number"},
                "costBurnUsd": {"type": "number"},
                "gpuName": {"type": "string"},
                "message": {"type": "string"},
            },
            "required": ["runId", "phase"],
        },
    },
    {
        "name": "crucible_record_compute_memory",
        "description": "Persist provider pricing, quota, compatibility, or run outcome evidence for future agents.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "runId": {"type": "string"},
                "provider": {"type": "string"},
                "gpuName": {"type": "string"},
                "region": {"type": "string"},
                "eventType": {"type": "string"},
                "status": {"type": "string"},
                "summary": {"type": "string"},
                "pricing": {"type": "object"},
                "compatibility": {"type": "object"},
            },
            "required": ["provider", "eventType", "status", "summary"],
        },
    },
    {
        "name": "crucible_publish_run_artifact",
        "description": "Attach storage artifact metadata and audit fields to an RL/GPU run capsule.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "runId": {"type": "string"},
                "kind": {"type": "string"},
                "uri": {"type": "string"},
                "metadata": {"type": "object"},
                "storageBucket": {"type": "string"},
            },
            "required": ["runId", "kind", "uri", "metadata"],
        },
    },
    {
        "name": "crucible_recommend_next_gpu_run",
        "description": "Ask the backend for the cheapest verified next RL/GPU run based on stored capsules and artifacts.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "envContractId": {"type": "string"},
                "objective": {"type": "string"},
            },
        },
    },
    {
        "name": "crucible_list_execution_features",
        "description": "Return the MCP execution matrix for RL environments, Modal smoke runs, and model deployments.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "crucible_claim_public_mcp_credit",
        "description": "Create or return a public MCP credit account. New callers receive the configured starter allowance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "callerId": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": ["callerId"],
        },
    },
    {
        "name": "crucible_public_mcp_credit_status",
        "description": "Return remaining public MCP run credits and usage events for a caller.",
        "inputSchema": {
            "type": "object",
            "properties": {"callerId": {"type": "string"}},
            "required": ["callerId"],
        },
    },
    {
        "name": "crucible_consume_public_mcp_credit",
        "description": "Reserve public MCP run credit before spendable server-side work. Secrets stay server-only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "callerId": {"type": "string"},
                "toolName": {"type": "string"},
                "runCount": {"type": "integer"},
                "metadata": {"type": "object"},
            },
            "required": ["callerId", "toolName"],
        },
    },
    {
        "name": "crucible_create_tensorlake_sandbox",
        "description": "Create a Tensorlake sandbox for isolated agent tool execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image": {"type": "string"},
                "cpus": {"type": "number"},
                "memoryMb": {"type": "integer"},
                "diskMb": {"type": "integer"},
                "timeoutSecs": {"type": "integer"},
                "name": {"type": "string"},
            },
        },
    },
    {
        "name": "crucible_run_tensorlake_command",
        "description": "Run a command inside an existing Tensorlake sandbox.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandboxId": {"type": "string"},
                "name": {"type": "string"},
                "command": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "timeoutSecs": {"type": "number"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "crucible_terminate_tensorlake_sandbox",
        "description": "Terminate a Tensorlake sandbox by ID or name.",
        "inputSchema": {
            "type": "object",
            "properties": {"sandboxId": {"type": "string"}, "name": {"type": "string"}},
        },
    },
    {
        "name": "crucible_list_tensorlake_sandboxes",
        "description": "List Tensorlake sandboxes visible to the configured API key.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "crucible_create_vcpu_host",
        "description": "Create a Tensorlake vCPU MicroVM for autonomous agent work or site hosting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "image": {"type": "string"},
                "cpus": {"type": "number"},
                "memoryMb": {"type": "integer"},
                "diskMb": {"type": "integer"},
                "timeoutSecs": {"type": "integer"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "crucible_run_vcpu_command",
        "description": "Run a command inside a Tensorlake vCPU host.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandboxId": {"type": "string"},
                "name": {"type": "string"},
                "command": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "timeoutSecs": {"type": "number"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "crucible_start_site",
        "description": "Start a long-running site command in a vCPU host and expose its port.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandboxId": {"type": "string"},
                "name": {"type": "string"},
                "command": {"type": "string"},
                "port": {"type": "integer"},
                "workingDir": {"type": "string"},
                "public": {"type": "boolean"},
            },
            "required": ["command", "port"],
        },
    },
    {
        "name": "crucible_expose_site_port",
        "description": "Expose a vCPU host port through Tensorlake networking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandboxId": {"type": "string"},
                "name": {"type": "string"},
                "port": {"type": "integer"},
                "public": {"type": "boolean"},
            },
            "required": ["port"],
        },
    },
    {
        "name": "crucible_get_site_status",
        "description": "Return status and public URL metadata for a vCPU-hosted site.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sandboxId": {"type": "string"},
                "name": {"type": "string"},
                "port": {"type": "integer"},
            },
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


def _tensorlake_adapter() -> Any:
    return importlib.import_module("anygpu.tensorlake_sandbox")


def handle_tool_call(store: Any, tool_name: str, arguments: JSON | None = None) -> JSON:
    arguments = arguments or {}
    try:
        if tool_name == "crucible_plan_deployment":
            plan = create_deployment_plan(
                store,
                _require(arguments, "userId"),
                _require(arguments, "prompt"),
                source=arguments.get("sourceAgent") or "mcp",
                model_id=arguments.get("modelId"),
                objective=arguments.get("objective"),
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
        if tool_name == "crucible_create_experiment_branch":
            return _ok(
                create_experiment_branch(
                    store,
                    name=_require(arguments, "name"),
                    parent_branch=arguments.get("parentBranch") or "main",
                    schema_snapshot=arguments.get("schemaSnapshot") or {},
                )
            )
        if tool_name == "crucible_merge_experiment_branch":
            return _ok(
                merge_experiment_branch(
                    store,
                    _require(arguments, "name"),
                    merge_note=_require(arguments, "mergeNote"),
                )
            )
        if tool_name == "crucible_create_environment_contract":
            return _ok(
                create_environment_contract(
                    store,
                    name=_require(arguments, "name"),
                    env_spec=_require(arguments, "envSpec"),
                    observation_schema=_require(arguments, "observationSchema"),
                    action_schema=_require(arguments, "actionSchema"),
                    reward_spec=_require(arguments, "rewardSpec"),
                    pass_criteria=_require(arguments, "passCriteria"),
                    branch_name=arguments.get("branchName") or "main",
                )
            )
        if tool_name == "crucible_request_gpu_run":
            return _ok(
                request_gpu_run(
                    store,
                    user_id=_require(arguments, "userId"),
                    prompt=_require(arguments, "prompt"),
                    env_contract_id=_require(arguments, "envContractId"),
                    provider_offers=_require(arguments, "providerOffers"),
                    cost_estimate=_require(arguments, "costEstimate"),
                    source_agent=arguments.get("sourceAgent") or "mcp",
                )
            )
        if tool_name == "crucible_list_run_capsules":
            return _ok(list_run_capsules(store))
        if tool_name == "crucible_approve_gpu_run":
            return _ok(
                approve_gpu_run(
                    store,
                    run_id=_require(arguments, "runId"),
                    approved_by=_require(arguments, "approvedBy"),
                    provider=_require(arguments, "provider"),
                    budget_usd=float(_require(arguments, "budgetUsd")),
                    max_runtime_minutes=int(_require(arguments, "maxRuntimeMinutes")),
                    teardown_policy=_require(arguments, "teardownPolicy"),
                )
            )
        if tool_name == "crucible_launch_gpu_run":
            launched = launch_gpu_run(
                store,
                _require(arguments, "runId"),
                approval_token=_require(arguments, "approvalToken"),
            )
            if arguments.get("execute") or arguments.get("executionMode") == "modal":
                mode = arguments.get("executionMode") or "modal"
                if mode != "modal":
                    raise ValueError(f"Unsupported executionMode {mode!r}.")
                return _ok(_execute_modal_rl_run(store, launched, arguments))
            return _ok(launched)
        if tool_name == "crucible_record_training_event":
            return _ok(
                record_training_event(
                    store,
                    run_id=_require(arguments, "runId"),
                    phase=_require(arguments, "phase"),
                    rollout_count=arguments.get("rolloutCount"),
                    reward_mean=arguments.get("rewardMean"),
                    success_rate=arguments.get("successRate"),
                    cost_burn_usd=arguments.get("costBurnUsd"),
                    gpu_name=arguments.get("gpuName"),
                    message=arguments.get("message") or "",
                )
            )
        if tool_name == "crucible_record_compute_memory":
            return _ok(
                record_compute_memory(
                    store,
                    run_id=arguments.get("runId"),
                    provider=_require(arguments, "provider"),
                    gpu_name=arguments.get("gpuName"),
                    region=arguments.get("region"),
                    event_type=_require(arguments, "eventType"),
                    status=_require(arguments, "status"),
                    summary=_require(arguments, "summary"),
                    pricing=arguments.get("pricing"),
                    compatibility=arguments.get("compatibility"),
                )
            )
        if tool_name == "crucible_publish_run_artifact":
            return _ok(
                publish_run_artifact(
                    store,
                    run_id=_require(arguments, "runId"),
                    kind=_require(arguments, "kind"),
                    uri=_require(arguments, "uri"),
                    metadata=_require(arguments, "metadata"),
                    storage_bucket=arguments.get("storageBucket") or "rl-runs",
                )
            )
        if tool_name == "crucible_recommend_next_gpu_run":
            return _ok(
                recommend_next_gpu_run(
                    store,
                    env_contract_id=arguments.get("envContractId"),
                    objective=arguments.get("objective") or "cheapest_verified_improving",
                )
            )
        if tool_name == "crucible_list_execution_features":
            return _ok(_execution_features())
        if tool_name == "crucible_claim_public_mcp_credit":
            return _ok(
                claim_public_mcp_credit(
                    store,
                    caller_id=_require(arguments, "callerId"),
                    label=arguments.get("label"),
                )
            )
        if tool_name == "crucible_public_mcp_credit_status":
            return _ok(public_mcp_credit_status(store, caller_id=_require(arguments, "callerId")))
        if tool_name == "crucible_consume_public_mcp_credit":
            return _ok(
                consume_public_mcp_credit(
                    store,
                    caller_id=_require(arguments, "callerId"),
                    tool_name=_require(arguments, "toolName"),
                    run_count=int(arguments.get("runCount", 1)),
                    metadata=arguments.get("metadata") or {},
                )
            )
        if tool_name == "crucible_create_tensorlake_sandbox":
            adapter = _tensorlake_adapter()
            create_args: dict[str, Any] = {}
            for json_key, adapter_key in (
                ("image", "image"),
                ("cpus", "cpus"),
                ("memoryMb", "memory_mb"),
                ("diskMb", "disk_mb"),
                ("timeoutSecs", "timeout_secs"),
                ("name", "name"),
            ):
                if json_key in arguments:
                    create_args[adapter_key] = arguments[json_key]
            return _ok(adapter.create_sandbox(**create_args))
        if tool_name == "crucible_run_tensorlake_command":
            return _ok(
                _tensorlake_adapter().run_command(
                    sandbox_id=arguments.get("sandboxId"),
                    name=arguments.get("name"),
                    command=_require(arguments, "command"),
                    args=arguments.get("args"),
                    timeout=arguments.get("timeoutSecs"),
                )
            )
        if tool_name == "crucible_terminate_tensorlake_sandbox":
            return _ok(
                _tensorlake_adapter().terminate_sandbox(
                    sandbox_id=arguments.get("sandboxId"),
                    name=arguments.get("name"),
                )
            )
        if tool_name == "crucible_list_tensorlake_sandboxes":
            return _ok(_tensorlake_adapter().list_sandboxes())
        if tool_name == "crucible_create_vcpu_host":
            adapter = _tensorlake_adapter()
            return _ok(
                adapter.create_vcpu_host(
                    name=_require(arguments, "name"),
                    image=arguments.get("image") or "tensorlake/ubuntu-minimal",
                    cpus=arguments.get("cpus", 1.0),
                    memory_mb=arguments.get("memoryMb", 2048),
                    disk_mb=arguments.get("diskMb", 10240),
                    timeout_secs=arguments.get("timeoutSecs", 3600),
                )
            )
        if tool_name == "crucible_run_vcpu_command":
            return _ok(
                _tensorlake_adapter().run_vcpu_command(
                    sandbox_id=arguments.get("sandboxId"),
                    name=arguments.get("name"),
                    command=_require(arguments, "command"),
                    args=arguments.get("args"),
                    timeout=arguments.get("timeoutSecs"),
                )
            )
        if tool_name == "crucible_start_site":
            return _ok(
                _tensorlake_adapter().start_site(
                    sandbox_id=arguments.get("sandboxId"),
                    name=arguments.get("name"),
                    command=_require(arguments, "command"),
                    port=int(_require(arguments, "port")),
                    working_dir=arguments.get("workingDir"),
                    public=arguments.get("public", True),
                )
            )
        if tool_name == "crucible_expose_site_port":
            return _ok(
                _tensorlake_adapter().expose_site_port(
                    sandbox_id=arguments.get("sandboxId"),
                    name=arguments.get("name"),
                    port=int(_require(arguments, "port")),
                    public=arguments.get("public", True),
                )
            )
        if tool_name == "crucible_get_site_status":
            return _ok(
                _tensorlake_adapter().get_site_status(
                    sandbox_id=arguments.get("sandboxId"),
                    name=arguments.get("name"),
                    port=arguments.get("port"),
                )
            )
        return _error(f"Unknown Crucible MCP tool: {tool_name}")
    except (ApprovalRequiredError, InsForgeApprovalRequiredError) as exc:
        return _error(str(exc))
    except ValueError as exc:
        return _error(str(exc))
