import json
import os
import httpx
from typing import List
from ..models import GpuOffer

BASE_URL = "https://console.vast.ai/api/v0"
MIN_VRAM_GB = 16
MIN_RELIABILITY = 0.95


def _api_key() -> str:
    api_key = os.environ.get("VAST_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("VAST_API_KEY is required.")
    return api_key


async def fetch() -> List[GpuOffer]:
    api_key = _api_key()
    params = {
        "q": {
            "gpu_ram": {"gte": MIN_VRAM_GB * 1024},  # vast uses MB
            "reliability2": {"gte": MIN_RELIABILITY},
            "rentable": {"eq": True},
            "num_gpus": {"gte": 1},
            "order": [["dph_total", "asc"]],
            "limit": 50,
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/bundles",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"q": json.dumps(params["q"])},
            follow_redirects=True,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    offers: List[GpuOffer] = []
    for offer in data.get("offers", []):
        vram_gb = int(offer.get("gpu_ram", 0) / 1024)
        if vram_gb < MIN_VRAM_GB:
            continue

        offers.append(GpuOffer(
            provider="vast",
            instance_id=str(offer["id"]),
            gpu_type=offer.get("gpu_name", "unknown"),
            gpu_count=offer.get("num_gpus", 1),
            vram_gb=vram_gb,
            price_per_hr=float(offer.get("dph_total", 0)),
            available=offer.get("rentable", False),
            region=offer.get("geolocation", "unknown"),
            raw=offer,
        ))

    return offers


async def launch(offer: GpuOffer, image: str = "pytorch/pytorch:2.1.0-cuda11.8-cudnn8-devel") -> dict:
    api_key = _api_key()
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{BASE_URL}/asks/{offer.instance_id}/",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "client_id": "me",
                "image": image,
                "disk": 50,
                "onstart": "",  # populated by deploy.py
                "runtype": "ssh_proxy",
                "extra_env": {},
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def terminate(contract_id: str) -> dict:
    api_key = _api_key()
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{BASE_URL}/instances/{contract_id}/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def get_instance(contract_id: str) -> dict:
    api_key = _api_key()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/instances/{contract_id}/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
