import os
import time
import httpx
from typing import List
from ..models import GpuOffer

GRAPHQL_URL = "https://api.runpod.io/graphql"
MIN_VRAM_GB = 16

_PRICE_QUERY = """
query GpuTypes {
  gpuTypes {
    id
    displayName
    memoryInGb
    lowestPrice(input: { gpuCount: 1 }) {
      minimumBidPrice
      uninterruptablePrice
    }
    communityCloud
    secureCloud
  }
}
"""


async def fetch() -> List[GpuOffer]:
    api_key = os.environ["RUNPOD_API_KEY"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRAPHQL_URL,
            json={"query": _PRICE_QUERY},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        _raise_graphql_errors(data)

    offers: List[GpuOffer] = []
    for gpu in data.get("data", {}).get("gpuTypes", []):
        vram_gb = gpu.get("memoryInGb", 0)
        if vram_gb < MIN_VRAM_GB:
            continue

        prices = gpu.get("lowestPrice", {}) or {}
        spot_price = prices.get("minimumBidPrice")
        on_demand_price = prices.get("uninterruptablePrice")

        if on_demand_price is None:
            continue
        price = float(on_demand_price)
        instance_id = f"ondemand:{gpu['id']}"

        offers.append(GpuOffer(
            provider="runpod",
            instance_id=instance_id,
            gpu_type=gpu.get("displayName", gpu["id"]),
            gpu_count=1,
            vram_gb=vram_gb,
            price_per_hr=price,
            available=True,
            region="global",
            raw=gpu,
        ))

    return offers


_DEPLOY_MUTATION = """
mutation PodFindAndDeployOnDemand($input: PodFindAndDeployOnDemandInput!) {
  podFindAndDeployOnDemand(input: $input) {
    id
    imageName
    env
    machineId
    machine { podHostId }
  }
}
"""


async def launch(offer: GpuOffer, image: str = "runpod/pytorch") -> dict:
    api_key = os.environ["RUNPOD_API_KEY"]
    gpu_id = offer.instance_id.split(":", 1)[1]

    variables = {
        "input": {
            "gpuTypeId": gpu_id,
            "cloudType": "ALL",
            "gpuCount": offer.gpu_count,
            "volumeInGb": 40,
            "containerDiskInGb": 40,
            "minVcpuCount": 2,
            "minMemoryInGb": 15,
            "name": f"anygpu-{int(time.time())}",
            "dockerArgs": "",
            "ports": "8000/http",
            "volumeMountPath": "/workspace",
            "imageName": image,
            "env": [],
        }
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRAPHQL_URL,
            json={"query": _DEPLOY_MUTATION, "variables": variables},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        _raise_graphql_errors(data)
        pod = data.get("data", {}).get("podFindAndDeployOnDemand")
        if not pod:
            raise RuntimeError(f"RunPod launch did not return a pod: {data}")
        return pod


_TERMINATE_MUTATION = """
mutation PodTerminate($input: PodTerminateInput!) {
  podTerminate(input: $input)
}
"""


async def terminate(pod_id: str) -> dict:
    api_key = os.environ["RUNPOD_API_KEY"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRAPHQL_URL,
            json={"query": _TERMINATE_MUTATION, "variables": {"input": {"podId": pod_id}}},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        _raise_graphql_errors(data)
        return data


def _raise_graphql_errors(data: dict) -> None:
    errors = data.get("errors") or []
    if errors:
        messages = "; ".join(str(error.get("message", error)) for error in errors)
        raise RuntimeError(f"RunPod GraphQL error: {messages}")
