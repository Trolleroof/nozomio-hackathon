import asyncio
import os
import secrets
import time
from typing import Optional

import httpx

from .models import GpuOffer, DeployedInstance
from .providers import lambda_labs, runpod, vast_ai, modal_gpu

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
VLLM_PORT = 8000

VLLM_BOOTSTRAP = """#!/bin/bash
set -e
pip install -q vllm huggingface_hub
vllm serve {model} \\
  --served-model-name qwen \\
  --host 0.0.0.0 \\
  --port {port} \\
  --api-key {api_key} \\
  --max-model-len 8192 &
# wait for server
for i in $(seq 1 60); do
  curl -sf http://localhost:{port}/v1/models && break
  sleep 10
done
""".strip()


def _generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


async def _wait_for_endpoint(url: str, api_key: Optional[str] = None, timeout: int = 600) -> bool:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    deadline = time.time() + timeout
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            try:
                resp = await client.get(f"{url}/models", headers=headers, timeout=5)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(15)
    return False


async def deploy(offer: GpuOffer) -> DeployedInstance:
    vllm_api_key = os.environ.get("VLLM_API_KEY") or _generate_api_key()
    bootstrap = VLLM_BOOTSTRAP.format(
        model=MODEL_ID, port=VLLM_PORT, api_key=vllm_api_key
    )

    if offer.provider == "lambda":
        return await _deploy_lambda(offer, vllm_api_key, bootstrap)
    elif offer.provider == "runpod":
        return await _deploy_runpod(offer, vllm_api_key)
    elif offer.provider == "vast":
        return await _deploy_vast(offer, vllm_api_key, bootstrap)
    elif offer.provider == "modal":
        return await _deploy_modal(offer, vllm_api_key)
    else:
        raise ValueError(f"Unknown provider: {offer.provider}")


async def _deploy_lambda(offer: GpuOffer, vllm_api_key: str, bootstrap: str) -> DeployedInstance:
    ssh_key = os.environ.get("LAMBDA_SSH_KEY_NAME", "default")
    result = await lambda_labs.launch(offer, ssh_key_name=ssh_key)
    instance_ids = result.get("data", {}).get("instance_ids", [])
    if not instance_ids:
        raise RuntimeError(f"Lambda launch failed: {result}")
    instance_id = instance_ids[0]

    # Poll until running and has IP
    ip = await _poll_lambda_ip(instance_id)
    await _ssh_bootstrap(ip, bootstrap)

    endpoint = f"http://{ip}:{VLLM_PORT}/v1"
    await _wait_for_endpoint(endpoint, api_key=vllm_api_key)

    return DeployedInstance(
        provider="lambda",
        instance_id=instance_id,
        gpu_type=offer.gpu_type,
        price_per_hr=offer.price_per_hr,
        endpoint_url=endpoint,
        api_key=vllm_api_key,
        deployed_at=time.time(),
        region=offer.region,
    )


async def _poll_lambda_ip(instance_id: str, timeout: int = 300) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = await lambda_labs.get_instance(instance_id)
        ip = info.get("ip")
        if ip and info.get("status") == "active":
            return ip
        await asyncio.sleep(15)
    raise TimeoutError(f"Lambda instance {instance_id} never became active")


async def _deploy_runpod(offer: GpuOffer, vllm_api_key: str) -> DeployedInstance:
    # RunPod: launch with vLLM docker image directly via env vars
    gpu_id = offer.instance_id.split(":", 1)[1]

    import httpx as _httpx
    api_key = _required_env("RUNPOD_API_KEY")
    mutation = """
    mutation PodFindAndDeployOnDemand($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) {
        id
        machine { podHostId }
        runtime { ports { ip isIpPublic privatePort publicPort type } }
      }
    }
    """
    variables = {
        "input": {
            "gpuTypeId": gpu_id,
            "cloudType": "SECURE",
            "gpuCount": offer.gpu_count,
            "volumeInGb": 40,
            "containerDiskInGb": 40,
            "minVcpuCount": 2,
            "minMemoryInGb": 15,
            "name": f"anygpu-{int(time.time())}",
            "volumeMountPath": "/workspace",
            "ports": f"{VLLM_PORT}/http",
            "imageName": "vllm/vllm-openai:latest",
            "dockerArgs": (
                f"--model {MODEL_ID} "
                f"--served-model-name qwen "
                f"--host 0.0.0.0 --port {VLLM_PORT} "
                f"--api-key {vllm_api_key} "
                f"--max-model-len 8192"
            ),
            "env": [{"key": "HUGGING_FACE_HUB_TOKEN", "value": os.environ.get("HF_TOKEN", "")}],
        }
    }
    async with _httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.runpod.io/graphql",
            json={"query": mutation, "variables": variables},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
        resp.raise_for_status()
        pod = resp.json().get("data", {}).get("podFindAndDeployOnDemand", {})

    pod_id = pod["id"]
    endpoint = await _poll_runpod_endpoint(pod_id, vllm_api_key)

    return DeployedInstance(
        provider="runpod",
        instance_id=pod_id,
        gpu_type=offer.gpu_type,
        price_per_hr=offer.price_per_hr,
        endpoint_url=endpoint,
        api_key=vllm_api_key,
        deployed_at=time.time(),
        region="global",
    )


async def _poll_runpod_endpoint(pod_id: str, vllm_api_key: str, timeout: int = 600) -> str:
    import httpx as _httpx
    api_key = _required_env("RUNPOD_API_KEY")
    query = """
    query Pod($podId: String!) {
      pod(input: { podId: $podId }) {
        id
        runtime { ports { ip isIpPublic privatePort publicPort type } }
      }
    }
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        async with _httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.runpod.io/graphql",
                json={"query": query, "variables": {"podId": pod_id}},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            data = resp.json().get("data", {}).get("pod", {})
            for port_info in (data.get("runtime") or {}).get("ports", []):
                if port_info.get("privatePort") == VLLM_PORT:
                    if port_info.get("isIpPublic"):
                        ip = port_info["ip"]
                        public_port = port_info["publicPort"]
                        url = f"http://{ip}:{public_port}/v1"
                    else:
                        url = f"https://{pod_id}-{VLLM_PORT}.proxy.runpod.net/v1"
                    if await _wait_for_endpoint(url, api_key=vllm_api_key, timeout=60):
                        return url
        await asyncio.sleep(20)
    raise TimeoutError(f"RunPod pod {pod_id} endpoint never became available")


async def _deploy_vast(offer: GpuOffer, vllm_api_key: str, bootstrap: str) -> DeployedInstance:
    result = await vast_ai.launch(offer)
    contract_id = str(result.get("new_contract", offer.instance_id))
    ip, port = await _poll_vast_ssh(contract_id)
    await _ssh_bootstrap(ip, bootstrap, port=port)

    endpoint = f"http://{ip}:{VLLM_PORT}/v1"
    await _wait_for_endpoint(endpoint, api_key=vllm_api_key)

    return DeployedInstance(
        provider="vast",
        instance_id=contract_id,
        gpu_type=offer.gpu_type,
        price_per_hr=offer.price_per_hr,
        endpoint_url=endpoint,
        api_key=vllm_api_key,
        deployed_at=time.time(),
        region=offer.region,
    )


async def _poll_vast_ssh(contract_id: str, timeout: int = 300) -> tuple[str, int]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = await vast_ai.get_instance(contract_id)
        instance = info.get("instances", {})
        if instance.get("actual_status") == "running":
            ip = instance.get("ssh_host")
            port = instance.get("ssh_port", 22)
            if ip:
                return ip, port
        await asyncio.sleep(15)
    raise TimeoutError(f"Vast.ai instance {contract_id} never became ready")


async def _deploy_modal(offer: GpuOffer, vllm_api_key: str) -> DeployedInstance:
    import subprocess, tempfile, json, pathlib

    gpu_type = offer.gpu_type
    script = modal_gpu.build_modal_app(gpu_type, vllm_api_key)

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(script)
        script_path = f.name

    env = {
        **os.environ,
        "MODAL_TOKEN_ID": _required_env("MODAL_TOKEN_ID"),
        "MODAL_TOKEN_SECRET": _required_env("MODAL_TOKEN_SECRET"),
    }
    result = subprocess.run(["modal", "deploy", script_path], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"modal deploy failed:\n{result.stderr}")

    # Parse endpoint URL from modal deploy output
    for line in result.stdout.splitlines():
        if "https://" in line and "modal.run" in line:
            endpoint = line.strip().split()[-1].rstrip("/") + "/v1"
            await _wait_for_endpoint(endpoint, api_key=vllm_api_key)
            return DeployedInstance(
                provider="modal",
                instance_id="modal:qwen-vllm",
                gpu_type=gpu_type,
                price_per_hr=offer.price_per_hr,
                endpoint_url=endpoint,
                api_key=vllm_api_key,
                deployed_at=time.time(),
                region="us-east",
            )

    raise RuntimeError("Could not parse Modal endpoint URL from deploy output")


async def _ssh_bootstrap(ip: str, script: str, port: int = 22) -> None:
    import asyncssh
    async with asyncssh.connect(
        ip,
        port=port,
        username="ubuntu",
        known_hosts=None,
        client_keys=[os.path.expanduser("~/.ssh/id_rsa")],
        connect_timeout=30,
    ) as conn:
        await conn.run(script, check=True)


async def teardown(instance: DeployedInstance) -> None:
    if instance.provider == "lambda":
        await lambda_labs.terminate(instance.instance_id)
    elif instance.provider == "runpod":
        await runpod.terminate(instance.instance_id)
    elif instance.provider == "vast":
        await vast_ai.terminate(instance.instance_id)
    elif instance.provider == "modal":
        import subprocess
        subprocess.run(["modal", "app", "stop", "qwen-vllm"], check=True)
    else:
        raise ValueError(f"Unknown provider: {instance.provider}")
