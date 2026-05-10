import asyncio
import importlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as error:
    if not (error.name or "").startswith("mcp"):
        raise

    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, name: str):
            self.name = name
            self.tools = {}

        def tool(self, *args, **_kwargs):
            def decorator(func):
                self.tools[func.__name__] = func
                return func

            if args and callable(args[0]):
                return decorator(args[0])
            return decorator

        def run(self) -> None:
            raise RuntimeError("The mcp package is required to run the MCP server.")

from .models import DeployedInstance
from .providers import fetch_lambda, fetch_runpod, fetch_vast, fetch_modal
from . import deploy as deploy_module
from . import monitor
from anygpu.crucible_mcp import handle_tool_call
from anygpu.crucible_store import CrucibleStore


def _create_mcp() -> FastMCP:
    try:
        return FastMCP("gpu-cheapest", stateless_http=True, json_response=True)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return FastMCP("gpu-cheapest")


mcp = _create_mcp()

# In-memory state — single active deployment per server session
_active: Optional[DeployedInstance] = None


def _load_local_dotenv() -> None:
    path = os.environ.get("ANYGPU_ENV_FILE", ".env")
    if not os.path.exists(path):
        return
    with open(path) as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip("'\"")


def _prepare_provider_environment() -> None:
    _load_local_dotenv()
    if "VAST_API_KEY" not in os.environ and "VAST_AI_API_KEY" in os.environ:
        os.environ["VAST_API_KEY"] = os.environ["VAST_AI_API_KEY"]


def _tensorlake_adapter():
    _load_local_dotenv()
    return importlib.import_module("anygpu.tensorlake_sandbox")


def _crucible_store():
    _load_local_dotenv()
    store_module = importlib.import_module("anygpu.crucible_store")
    return store_module.CrucibleStore()


def _call_crucible_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    mcp_module = importlib.import_module("anygpu.crucible_mcp")
    return json.dumps(mcp_module.handle_tool_call(_crucible_store(), tool_name, arguments), indent=2)


def _anygpu_gateway_endpoint() -> Optional[dict]:
    try:
        domain = importlib.import_module("anygpu.domain")
        state_module = importlib.import_module("anygpu.state")
        state = state_module.load_state()
    except Exception:
        return None
    deployments = [
        deployment
        for deployment in state.get("deployments", {}).values()
        if deployment.get("health") != "stopped"
    ]
    if not deployments:
        return None
    deployment = sorted(deployments, key=lambda item: item.get("created_at", ""))[-1]
    contract = deployment.get("gateway") or domain.gateway_contract(deployment["name"])
    endpoint = {
        "base_url": contract["base_url"],
        "model": contract["model"],
    }
    if deployment.get("upstream_url"):
        endpoint["upstream_url"] = deployment["upstream_url"]
    return endpoint


def _register_anygpu_gateway_route(
    instance: DeployedInstance,
    deployment_name: str = "local-chat",
    served_model: str = "qwen",
) -> dict:
    domain = importlib.import_module("anygpu.domain")
    state_module = importlib.import_module("anygpu.state")
    contract = domain.gateway_contract(deployment_name)
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    endpoint_url = instance.endpoint_url.rstrip("/")
    runtime_url = endpoint_url.removesuffix("/v1")
    upstream_chat_url = f"{endpoint_url}/chat/completions"
    route = {
        "role": "primary",
        "route": f"mcp:{instance.provider}:{instance.instance_id}",
        "pool": f"mcp:{instance.provider}",
        "runtime": "vllm",
        "status": "healthy",
        "simulated": False,
        "real": True,
        "upstream_url": runtime_url,
        "runtime_url": runtime_url,
        "upstream_api_key": instance.api_key,
        "p95_ms": 0,
        "tokens_per_sec": 0,
        "estimated_cost": instance.price_per_hr,
    }
    with state_module.edit_state() as state:
        state["deployments"][deployment_name] = {
            "name": deployment_name,
            "kind": "mcp-runtime",
            "provider": instance.provider,
            "compute": f"mcp:{instance.provider}",
            "model": served_model,
            "model_source": deploy_module.MODEL_ID,
            "runtime": "vllm",
            "endpoint": "openai",
            "gateway": contract,
            "url": contract["chat_completions_url"],
            "upstream_url": upstream_chat_url,
            "health": "healthy",
            "created_at": created_at,
            "runtime_process": {
                "provider": instance.provider,
                "instance_id": instance.instance_id,
                "gpu_type": instance.gpu_type,
                "region": instance.region,
                "price_per_hr": instance.price_per_hr,
                "upstream_url": runtime_url,
                "endpoint_url": endpoint_url,
                "api_key": instance.api_key,
                "health": "healthy",
            },
            "routes": [route],
        }
    return {
        "base_url": contract["base_url"],
        "model": contract["model"],
        "chat_completions_url": contract["chat_completions_url"],
        "upstream_url": upstream_chat_url,
    }


def _configure_http_transport() -> None:
    mcp.settings.host = os.environ.get("MCP_HOST", "127.0.0.1")
    mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True
    allowed_hosts = os.environ.get("MCP_ALLOWED_HOSTS")
    if allowed_hosts:
        mcp.settings.transport_security.allowed_hosts = [
            host.strip() for host in allowed_hosts.split(",") if host.strip()
        ]


def _crucible_tool(tool_name: str, arguments: dict | None = None) -> str:
    return json.dumps(handle_tool_call(CrucibleStore(), tool_name, arguments or {}), indent=2)


@mcp.tool()
async def list_gpu_prices(min_vram_gb: int = 16, top_n: int = 10) -> str:
    """Query all GPU cloud providers and return the cheapest available options.

    Args:
        min_vram_gb: Minimum VRAM required (default 16 GB for Qwen 2.5-7B).
        top_n: How many offers to return (default 10).
    """
    _prepare_provider_environment()
    results = await asyncio.gather(
        fetch_lambda(),
        fetch_runpod(),
        fetch_vast(),
        fetch_modal(),
        return_exceptions=True,
    )

    offers = []
    errors = []
    for r in results:
        if isinstance(r, Exception):
            errors.append(str(r))
        else:
            offers.extend(r)

    filtered = [o for o in offers if o.vram_gb >= min_vram_gb and o.available]
    filtered.sort(key=lambda o: o.price_per_hr)

    output = {
        "offers": [o.to_dict() for o in filtered[:top_n]],
        "total_found": len(filtered),
    }
    if errors:
        output["provider_errors"] = errors

    return json.dumps(output, indent=2)


@mcp.tool()
async def check_availability(provider: Optional[str] = None, min_vram_gb: int = 16) -> str:
    """Check which GPU instances are currently available.

    Args:
        provider: Filter to a specific provider ("lambda", "runpod", "vast", "modal"). Omit for all.
        min_vram_gb: Minimum VRAM filter.
    """
    _prepare_provider_environment()
    fetchers = {
        "lambda": fetch_lambda,
        "runpod": fetch_runpod,
        "vast": fetch_vast,
        "modal": fetch_modal,
    }
    selected = {k: v for k, v in fetchers.items() if provider is None or k == provider}

    results = await asyncio.gather(*[f() for f in selected.values()], return_exceptions=True)

    available = []
    for r in results:
        if not isinstance(r, Exception):
            available.extend(o.to_dict() for o in r if o.available and o.vram_gb >= min_vram_gb)

    available.sort(key=lambda o: o["price_per_hr"])
    return json.dumps({"available": available, "count": len(available)}, indent=2)


@mcp.tool()
async def deploy_cheapest(min_vram_gb: int = 16, provider: Optional[str] = None) -> str:
    """Provision the cheapest available GPU and start vLLM serving Qwen 2.5-7B.

    Blocks until the OpenAI-compatible endpoint is healthy (up to ~10 minutes).

    Args:
        min_vram_gb: Minimum VRAM (default 16 GB).
        provider: Force a specific provider. Omit to auto-select cheapest.
    """
    global _active
    if _active is not None:
        return json.dumps({"error": "An instance is already running. Call teardown() first."})

    _prepare_provider_environment()
    fetchers = [fetch_lambda, fetch_runpod, fetch_vast, fetch_modal]
    results = await asyncio.gather(*[f() for f in fetchers], return_exceptions=True)

    offers = []
    for r in results:
        if not isinstance(r, Exception):
            offers.extend(r)

    filtered = [
        o for o in offers
        if o.vram_gb >= min_vram_gb and o.available and (provider is None or o.provider == provider)
    ]
    if not filtered:
        return json.dumps({"error": "No available instances match the criteria."})

    filtered.sort(key=lambda o: o.price_per_hr)
    best = filtered[0]

    instance = await deploy_module.deploy(best)
    _active = instance
    gateway = _register_anygpu_gateway_route(instance)

    return json.dumps({
        "status": "deployed",
        "provider": instance.provider,
        "instance_id": instance.instance_id,
        "gpu_type": instance.gpu_type,
        "price_per_hr": instance.price_per_hr,
        "gateway": gateway,
        "upstream_endpoint_url": instance.endpoint_url,
        "api_key": instance.api_key,
    }, indent=2)


@mcp.tool()
async def get_endpoint() -> str:
    """Return the OpenAI-compatible AnyGPU gateway base URL and model."""
    endpoint = _anygpu_gateway_endpoint()
    if endpoint is not None:
        return json.dumps(endpoint, indent=2)
    if _active is None:
        return json.dumps({"error": "No active deployment. Call deploy_cheapest() first."})
    return json.dumps({
        "base_url": _active.endpoint_url,
        "api_key": _active.api_key,
        "model": "qwen",
    }, indent=2)


@mcp.tool()
async def get_spend() -> str:
    """Return current running cost and uptime for the active deployment."""
    if _active is None:
        return json.dumps({"error": "No active deployment."})
    return json.dumps(monitor.get_spend(_active), indent=2)


@mcp.tool()
async def teardown() -> str:
    """Terminate the active GPU instance and stop vLLM."""
    global _active
    if _active is None:
        return json.dumps({"error": "No active deployment to tear down."})

    spend = monitor.get_spend(_active)
    await deploy_module.teardown(_active)
    _active = None

    return json.dumps({"status": "terminated", "final_spend": spend}, indent=2)


@mcp.tool()
def crucible_plan_deployment(
    userId: str,
    prompt: str,
    sourceAgent: Optional[str] = None,
    modelId: Optional[str] = None,
    objective: Optional[str] = None,
) -> str:
    """Create a Crucible GPU deployment plan from a natural-language request."""
    return _call_crucible_tool(
        "crucible_plan_deployment",
        {
            "userId": userId,
            "prompt": prompt,
            "sourceAgent": sourceAgent,
            "modelId": modelId,
            "objective": objective,
        },
    )


@mcp.tool()
def crucible_approve_plan(planId: str, userId: str) -> str:
    """Record explicit approval before launching planned GPU resources."""
    return _call_crucible_tool(
        "crucible_approve_plan",
        {
            "planId": planId,
            "userId": userId,
        },
    )


@mcp.tool()
def crucible_deploy_approved_plan(planId: str, approvalToken: Optional[str] = None) -> str:
    """Deploy an approved Crucible plan, enforcing the approval token gate."""
    return _call_crucible_tool(
        "crucible_deploy_approved_plan",
        {
            "planId": planId,
            "approvalToken": approvalToken,
        },
    )


@mcp.tool()
def crucible_get_deployment_status(deploymentId: str) -> str:
    """Fetch Crucible deployment status and endpoint metadata."""
    return _call_crucible_tool("crucible_get_deployment_status", {"deploymentId": deploymentId})


@mcp.tool()
def crucible_get_logs(deploymentId: str) -> str:
    """Fetch Crucible deployment lifecycle logs."""
    return _call_crucible_tool("crucible_get_logs", {"deploymentId": deploymentId})


@mcp.tool()
def crucible_run_health_check(deploymentId: str) -> str:
    """Run the stored Crucible deployment health-check workflow."""
    return _call_crucible_tool("crucible_run_health_check", {"deploymentId": deploymentId})


@mcp.tool()
def crucible_stop_deployment(deploymentId: str) -> str:
    """Stop a Crucible deployment record and append stop logs."""
    return _call_crucible_tool("crucible_stop_deployment", {"deploymentId": deploymentId})


@mcp.tool()
def crucible_create_experiment_branch(
    name: str,
    parentBranch: Optional[str] = None,
    schemaSnapshot: Optional[dict[str, Any]] = None,
) -> str:
    """Create an isolated InsForge-style experiment branch for RL environment or workflow changes."""
    return _call_crucible_tool(
        "crucible_create_experiment_branch",
        {
            "name": name,
            "parentBranch": parentBranch,
            "schemaSnapshot": schemaSnapshot,
        },
    )


@mcp.tool()
def crucible_create_environment_contract(
    name: str,
    envSpec: dict[str, Any],
    observationSchema: dict[str, Any],
    actionSchema: dict[str, Any],
    rewardSpec: dict[str, Any],
    passCriteria: dict[str, Any],
    branchName: Optional[str] = None,
) -> str:
    """Create an agent-readable RL environment contract."""
    return _call_crucible_tool(
        "crucible_create_environment_contract",
        {
            "name": name,
            "envSpec": envSpec,
            "observationSchema": observationSchema,
            "actionSchema": actionSchema,
            "rewardSpec": rewardSpec,
            "passCriteria": passCriteria,
            "branchName": branchName,
        },
    )


@mcp.tool()
def crucible_request_gpu_run(
    userId: str,
    prompt: str,
    envContractId: str,
    providerOffers: list[dict[str, Any]],
    costEstimate: dict[str, Any],
    sourceAgent: Optional[str] = None,
) -> str:
    """Create a durable RL/GPU run capsule that cannot launch until approved."""
    return _call_crucible_tool(
        "crucible_request_gpu_run",
        {
            "userId": userId,
            "prompt": prompt,
            "envContractId": envContractId,
            "providerOffers": providerOffers,
            "costEstimate": costEstimate,
            "sourceAgent": sourceAgent,
        },
    )


@mcp.tool()
def crucible_approve_gpu_run(
    runId: str,
    approvedBy: str,
    provider: str,
    budgetUsd: float,
    maxRuntimeMinutes: int,
    teardownPolicy: dict[str, Any],
) -> str:
    """Create the signed approval ledger row required before a paid RL/GPU run launches."""
    return _call_crucible_tool(
        "crucible_approve_gpu_run",
        {
            "runId": runId,
            "approvedBy": approvedBy,
            "provider": provider,
            "budgetUsd": budgetUsd,
            "maxRuntimeMinutes": maxRuntimeMinutes,
            "teardownPolicy": teardownPolicy,
        },
    )


@mcp.tool()
def crucible_launch_gpu_run(
    runId: str,
    approvalToken: str,
    execute: bool = False,
    executionMode: Optional[str] = None,
    gpu: Optional[str] = None,
    updates: Optional[int] = None,
    nEnvs: Optional[int] = None,
    rolloutSteps: Optional[int] = None,
    ppoEpochs: Optional[int] = None,
    minibatchSize: Optional[int] = None,
) -> str:
    """Launch an approved RL/GPU run capsule, optionally executing the Modal RL smoke."""
    return _call_crucible_tool(
        "crucible_launch_gpu_run",
        {
            "runId": runId,
            "approvalToken": approvalToken,
            "execute": execute,
            "executionMode": executionMode,
            "gpu": gpu,
            "updates": updates,
            "nEnvs": nEnvs,
            "rolloutSteps": rolloutSteps,
            "ppoEpochs": ppoEpochs,
            "minibatchSize": minibatchSize,
        },
    )


@mcp.tool()
def crucible_record_training_event(
    runId: str,
    phase: str,
    rolloutCount: Optional[int] = None,
    rewardMean: Optional[float] = None,
    successRate: Optional[float] = None,
    costBurnUsd: Optional[float] = None,
    gpuName: Optional[str] = None,
    message: str = "",
) -> str:
    """Append realtime-style training progress for an RL/GPU run capsule."""
    return _call_crucible_tool(
        "crucible_record_training_event",
        {
            "runId": runId,
            "phase": phase,
            "rolloutCount": rolloutCount,
            "rewardMean": rewardMean,
            "successRate": successRate,
            "costBurnUsd": costBurnUsd,
            "gpuName": gpuName,
            "message": message,
        },
    )


@mcp.tool()
def crucible_record_compute_memory(
    provider: str,
    eventType: str,
    status: str,
    summary: str,
    runId: Optional[str] = None,
    gpuName: Optional[str] = None,
    region: Optional[str] = None,
    pricing: Optional[dict[str, Any]] = None,
    compatibility: Optional[dict[str, Any]] = None,
) -> str:
    """Persist provider pricing, quota, compatibility, or run outcome evidence for future agents."""
    return _call_crucible_tool(
        "crucible_record_compute_memory",
        {
            "runId": runId,
            "provider": provider,
            "gpuName": gpuName,
            "region": region,
            "eventType": eventType,
            "status": status,
            "summary": summary,
            "pricing": pricing,
            "compatibility": compatibility,
        },
    )


@mcp.tool()
def crucible_publish_run_artifact(
    runId: str,
    kind: str,
    uri: str,
    metadata: dict[str, Any],
    storageBucket: Optional[str] = None,
) -> str:
    """Attach storage artifact metadata and audit fields to an RL/GPU run capsule."""
    return _call_crucible_tool(
        "crucible_publish_run_artifact",
        {
            "runId": runId,
            "kind": kind,
            "uri": uri,
            "metadata": metadata,
            "storageBucket": storageBucket,
        },
    )


@mcp.tool()
def crucible_recommend_next_gpu_run(
    envContractId: Optional[str] = None,
    objective: Optional[str] = None,
) -> str:
    """Recommend the cheapest verified next RL/GPU run from stored capsules and artifacts."""
    return _call_crucible_tool(
        "crucible_recommend_next_gpu_run",
        {
            "envContractId": envContractId,
            "objective": objective,
        },
    )


@mcp.tool()
def create_tensorlake_sandbox(
    image: str = "tensorlake/ubuntu-minimal",
    cpus: float = 1.0,
    memory_mb: int = 1024,
    disk_mb: int = 10240,
    timeout_secs: int = 300,
    name: Optional[str] = None,
) -> str:
    """Create a Tensorlake MicroVM sandbox for isolated agent tool execution."""
    return json.dumps(
        _tensorlake_adapter().create_sandbox(
            image=image,
            cpus=cpus,
            memory_mb=memory_mb,
            disk_mb=disk_mb,
            timeout_secs=timeout_secs,
            name=name,
        ),
        indent=2,
    )


@mcp.tool()
def run_tensorlake_command(
    command: str,
    sandbox_id: Optional[str] = None,
    name: Optional[str] = None,
    args: Optional[list[str]] = None,
    timeout: Optional[float] = None,
) -> str:
    """Run a command inside a Tensorlake sandbox by sandbox ID or name."""
    return json.dumps(
        _tensorlake_adapter().run_command(
            sandbox_id=sandbox_id,
            name=name,
            command=command,
            args=args,
            timeout=timeout,
        ),
        indent=2,
    )


@mcp.tool()
def list_tensorlake_sandboxes() -> str:
    """List Tensorlake sandboxes visible to the configured API key."""
    return json.dumps(_tensorlake_adapter().list_sandboxes(), indent=2)


@mcp.tool()
def terminate_tensorlake_sandbox(sandbox_id: Optional[str] = None, name: Optional[str] = None) -> str:
    """Terminate a Tensorlake sandbox by sandbox ID or name."""
    return json.dumps(
        _tensorlake_adapter().terminate_sandbox(sandbox_id=sandbox_id, name=name),
        indent=2,
    )


@mcp.tool()
def create_vcpu_host(
    name: str,
    image: str = "tensorlake/ubuntu-minimal",
    cpus: float = 1.0,
    memory_mb: int = 2048,
    disk_mb: int = 10240,
    timeout_secs: int = 3600,
) -> str:
    """Create a Tensorlake vCPU MicroVM for autonomous agent work or site hosting."""
    return json.dumps(
        _tensorlake_adapter().create_vcpu_host(
            name=name,
            image=image,
            cpus=cpus,
            memory_mb=memory_mb,
            disk_mb=disk_mb,
            timeout_secs=timeout_secs,
        ),
        indent=2,
    )


@mcp.tool()
def run_vcpu_command(
    command: str,
    sandbox_id: Optional[str] = None,
    name: Optional[str] = None,
    args: Optional[list[str]] = None,
    timeout: Optional[float] = None,
) -> str:
    """Run a command inside a Tensorlake vCPU host."""
    return json.dumps(
        _tensorlake_adapter().run_vcpu_command(
            sandbox_id=sandbox_id,
            name=name,
            command=command,
            args=args,
            timeout=timeout,
        ),
        indent=2,
    )


@mcp.tool()
def start_site(
    command: str,
    port: int,
    sandbox_id: Optional[str] = None,
    name: Optional[str] = None,
    working_dir: Optional[str] = None,
    public: bool = True,
) -> str:
    """Start a long-running site command in a vCPU host and expose its port."""
    return json.dumps(
        _tensorlake_adapter().start_site(
            sandbox_id=sandbox_id,
            name=name,
            command=command,
            port=port,
            working_dir=working_dir,
            public=public,
        ),
        indent=2,
    )


@mcp.tool()
def expose_site_port(
    port: int,
    sandbox_id: Optional[str] = None,
    name: Optional[str] = None,
    public: bool = True,
) -> str:
    """Expose a vCPU host port through Tensorlake networking."""
    return json.dumps(
        _tensorlake_adapter().expose_site_port(sandbox_id=sandbox_id, name=name, port=port, public=public),
        indent=2,
    )


@mcp.tool()
def get_site_status(sandbox_id: Optional[str] = None, name: Optional[str] = None, port: Optional[int] = None) -> str:
    """Return status and public URL metadata for a vCPU-hosted site."""
    return json.dumps(_tensorlake_adapter().get_site_status(sandbox_id=sandbox_id, name=name, port=port), indent=2)


@mcp.tool()
def crucible_list_deployments() -> str:
    """List Crucible deployments recorded through the Hermes/Crucible MCP control plane."""
    return _crucible_tool("crucible_list_deployments")


@mcp.tool()
def crucible_create_environment_contract(
    name: str,
    env_spec: dict,
    observation_schema: dict,
    action_schema: dict,
    reward_spec: dict,
    pass_criteria: dict,
    branch_name: str = "main",
) -> str:
    """Create an RL environment contract before a Hermes-triggered training run."""
    return _crucible_tool(
        "crucible_create_environment_contract",
        {
            "name": name,
            "envSpec": env_spec,
            "observationSchema": observation_schema,
            "actionSchema": action_schema,
            "rewardSpec": reward_spec,
            "passCriteria": pass_criteria,
            "branchName": branch_name,
        },
    )


@mcp.tool()
def crucible_request_gpu_run(
    user_id: str,
    prompt: str,
    env_contract_id: str,
    provider_offers: list[dict],
    cost_estimate: dict,
    source_agent: str = "hermes",
) -> str:
    """Create a durable RL/GPU run capsule from Hermes or another MCP client."""
    return _crucible_tool(
        "crucible_request_gpu_run",
        {
            "userId": user_id,
            "prompt": prompt,
            "envContractId": env_contract_id,
            "providerOffers": provider_offers,
            "costEstimate": cost_estimate,
            "sourceAgent": source_agent,
        },
    )


@mcp.tool()
def crucible_list_run_capsules() -> str:
    """List RL/GPU run capsules for the dashboard and Hermes agent."""
    return _crucible_tool("crucible_list_run_capsules")


@mcp.tool()
def crucible_approve_gpu_run(
    run_id: str,
    approved_by: str,
    provider: str,
    budget_usd: float,
    max_runtime_minutes: int,
    teardown_policy: dict,
) -> str:
    """Create the signed approval ledger row required before a paid GPU run launches."""
    return _crucible_tool(
        "crucible_approve_gpu_run",
        {
            "runId": run_id,
            "approvedBy": approved_by,
            "provider": provider,
            "budgetUsd": budget_usd,
            "maxRuntimeMinutes": max_runtime_minutes,
            "teardownPolicy": teardown_policy,
        },
    )


@mcp.tool()
def crucible_launch_gpu_run(run_id: str, approval_token: str) -> str:
    """Mark an RL/GPU run capsule running only after signed approval is present."""
    return _crucible_tool("crucible_launch_gpu_run", {"runId": run_id, "approvalToken": approval_token})


@mcp.tool()
def crucible_record_training_event(
    run_id: str,
    phase: str,
    rollout_count: Optional[int] = None,
    reward_mean: Optional[float] = None,
    success_rate: Optional[float] = None,
    cost_burn_usd: Optional[float] = None,
    gpu_name: Optional[str] = None,
    message: str = "",
) -> str:
    """Append realtime-style training progress for a run capsule displayed on the dashboard."""
    return _crucible_tool(
        "crucible_record_training_event",
        {
            "runId": run_id,
            "phase": phase,
            "rolloutCount": rollout_count,
            "rewardMean": reward_mean,
            "successRate": success_rate,
            "costBurnUsd": cost_burn_usd,
            "gpuName": gpu_name,
            "message": message,
        },
    )


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in {"streamable-http", "streamable_http", "http"}:
        _configure_http_transport()
        mcp.settings.streamable_http_path = os.environ.get("MCP_PATH", "/mcp")
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        _configure_http_transport()
        mcp.settings.mount_path = os.environ.get("MCP_PATH", "/sse")
        mcp.run(transport="sse", mount_path=mcp.settings.mount_path)
    else:
        mcp.run()
