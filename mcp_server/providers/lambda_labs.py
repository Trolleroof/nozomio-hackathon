import os
import httpx
from typing import List
from ..models import GpuOffer

BASE_URL = "https://cloud.lambdalabs.com/api/v1"
MIN_VRAM_GB = 16


async def fetch() -> List[GpuOffer]:
    api_key = os.environ["LAMBDA_API_KEY"]
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/instance-types",
            auth=(api_key, ""),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    offers: List[GpuOffer] = []
    for name, info in data.get("data", {}).items():
        specs = info.get("instance_type", {})
        gpu_specs = specs.get("specs", {})
        gpu_memory_mb = gpu_specs.get("gpu_memory_gib", 0) * 1024  # already GiB label
        vram_gb = gpu_specs.get("gpu_memory_gib", 0)
        gpu_count = gpu_specs.get("gpus", 1)
        price = specs.get("price_cents_per_hour", 0) / 100.0

        if vram_gb < MIN_VRAM_GB:
            continue

        regions_available = info.get("regions_with_capacity_available", [])
        available = len(regions_available) > 0
        region = regions_available[0].get("name", "unknown") if regions_available else "unknown"

        offers.append(GpuOffer(
            provider="lambda",
            instance_id=name,
            gpu_type=specs.get("description", name),
            gpu_count=gpu_count,
            vram_gb=vram_gb,
            price_per_hr=price,
            available=available,
            region=region,
            raw=info,
        ))

    return offers


async def launch(offer: GpuOffer, ssh_key_name: str) -> dict:
    api_key = os.environ["LAMBDA_API_KEY"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/instance-operations/launch",
            auth=(api_key, ""),
            json={
                "region_name": offer.region,
                "instance_type_name": offer.instance_id,
                "ssh_key_names": [ssh_key_name],
                "quantity": 1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def terminate(instance_id: str) -> dict:
    api_key = os.environ["LAMBDA_API_KEY"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/instance-operations/terminate",
            auth=(api_key, ""),
            json={"instance_ids": [instance_id]},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def get_instance(instance_id: str) -> dict:
    api_key = os.environ["LAMBDA_API_KEY"]
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/instances/{instance_id}",
            auth=(api_key, ""),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", {})
