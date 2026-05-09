import asyncio
import importlib
import json
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .models import DeployedInstance
from .providers import fetch_lambda, fetch_runpod, fetch_vast, fetch_modal
from . import deploy as deploy_module
from . import monitor

mcp = FastMCP("gpu-cheapest")

# In-memory state — single active deployment per server session
_active: Optional[DeployedInstance] = None


def _tensorlake_adapter():
    return importlib.import_module("anygpu.tensorlake_sandbox")


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


@mcp.tool()
async def list_gpu_prices(min_vram_gb: int = 16, top_n: int = 10) -> str:
    """Query all GPU cloud providers and return the cheapest available options.

    Args:
        min_vram_gb: Minimum VRAM required (default 16 GB for Qwen 2.5-7B).
        top_n: How many offers to return (default 10).
    """
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

    return json.dumps({
        "status": "deployed",
        "provider": instance.provider,
        "instance_id": instance.instance_id,
        "gpu_type": instance.gpu_type,
        "price_per_hr": instance.price_per_hr,
        "endpoint_url": instance.endpoint_url,
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


if __name__ == "__main__":
    mcp.run()
