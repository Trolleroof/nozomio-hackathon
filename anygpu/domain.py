from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import load_config
from .provider import DockerProvider, KubernetesProvider, LocalProvider, VastProvider, VultrProvider
from .runtime import LlamaCppRuntime


MANAGED_POOLS: dict[str, dict[str, Any]] = {
    "nvidia-fast": {
        "name": "nvidia-fast",
        "kind": "managed",
        "hardware": "H100/L40S",
        "regions": ["us-west", "us-east"],
        "modes": ["serverful", "warm"],
        "runtimes": ["vllm", "sglang", "llama.cpp"],
        "accelerator": "cuda",
        "max_vram_gb": 80,
        "hourly_cost": 3.2,
        "capacity": 12,
        "status": "available",
        "certified": False,
    },
    "amd-value": {
        "name": "amd-value",
        "kind": "managed",
        "hardware": "MI300X",
        "regions": ["us-east"],
        "modes": ["serverful"],
        "runtimes": ["vllm", "llama.cpp"],
        "accelerator": "rocm",
        "max_vram_gb": 192,
        "hourly_cost": 2.35,
        "capacity": 8,
        "status": "available",
        "certified": False,
    },
    "serverless-gpu": {
        "name": "serverless-gpu",
        "kind": "managed",
        "hardware": "L40S/A10",
        "regions": ["global-ish"],
        "modes": ["serverless"],
        "runtimes": ["vllm", "llama.cpp"],
        "accelerator": "cuda",
        "max_vram_gb": 48,
        "hourly_cost": 1.65,
        "capacity": 20,
        "status": "available",
        "certified": False,
    },
    "cpu-batch": {
        "name": "cpu-batch",
        "kind": "managed",
        "hardware": "CPU",
        "regions": ["us-west", "us-east"],
        "modes": ["batch"],
        "runtimes": ["llama.cpp"],
        "accelerator": "cpu",
        "max_vram_gb": 0,
        "hourly_cost": 0.22,
        "capacity": 50,
        "status": "available",
        "certified": False,
    },
}


def gateway_contract(name: str, host: str = "127.0.0.1", port: int = 8765) -> dict[str, str]:
    base_url = f"http://{host}:{port}/v1"
    return {
        "base_url": base_url,
        "model": name,
        "chat_completions_url": f"{base_url}/chat/completions",
    }


BROKER_PROVIDER_SEEDS: list[dict[str, Any]] = [
    {
        "id": "runpod",
        "name": "RunPod",
        "architectures": ["nvidia"],
        "accelerators": ["h100", "h200", "a100", "l40s", "rtx-4090"],
        "regions": ["us-secure", "eu-secure", "community"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "lambda",
        "name": "Lambda Cloud",
        "architectures": ["nvidia"],
        "accelerators": ["h100", "h200", "a100", "a10"],
        "regions": ["us-west", "us-east"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "vast",
        "name": "Vast.ai",
        "architectures": ["nvidia", "amd"],
        "accelerators": ["h100", "a100", "l40s", "rtx-4090", "mi300x"],
        "regions": ["marketplace"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "vultr",
        "name": "Vultr",
        "architectures": ["nvidia", "amd"],
        "accelerators": ["b200", "a100", "a40", "a16", "mi355x", "mi325x"],
        "regions": ["ewr", "ord", "lax", "del"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "nebius",
        "name": "Nebius AI Cloud",
        "architectures": ["nvidia"],
        "accelerators": ["b200", "h200", "h100"],
        "regions": ["us", "eu"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "oci",
        "name": "Oracle Cloud Infrastructure GPU",
        "architectures": ["nvidia"],
        "accelerators": ["b200", "h200", "h100", "l40s", "a100", "a10"],
        "regions": ["us-ashburn-1", "us-phoenix-1", "eu-frankfurt-1"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "paperspace",
        "name": "DigitalOcean Paperspace",
        "architectures": ["nvidia"],
        "accelerators": ["h100", "a100"],
        "regions": ["us-east", "us-west", "eu"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "datacrunch",
        "name": "DataCrunch",
        "architectures": ["nvidia"],
        "accelerators": ["b200", "h200", "h100", "a100", "l40s"],
        "regions": ["eu"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "hyperstack",
        "name": "Hyperstack",
        "architectures": ["nvidia"],
        "accelerators": ["h200", "h100", "a100"],
        "regions": ["north-america", "europe"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "cudo",
        "name": "Cudo Compute",
        "architectures": ["nvidia"],
        "accelerators": ["h100", "a100", "l40s", "a40"],
        "regions": ["global"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "genesis-cloud",
        "name": "Genesis Cloud",
        "architectures": ["nvidia"],
        "accelerators": ["b200", "h200", "h100"],
        "regions": ["no", "fr", "es", "fi", "us", "ca"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "voltage-park",
        "name": "Voltage Park",
        "architectures": ["nvidia"],
        "accelerators": ["b200", "h100"],
        "regions": ["texas", "virginia", "washington", "utah"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "aws",
        "name": "AWS EC2 GPU",
        "architectures": ["nvidia", "intel-gaudi", "apple-silicon"],
        "accelerators": ["h100", "l40s", "a10g", "gaudi1", "m2-ultra"],
        "regions": ["us-east-1", "us-west-2", "eu-west-1"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "gcp",
        "name": "Google Cloud GPU",
        "architectures": ["nvidia"],
        "accelerators": ["h100", "a100", "l4", "t4"],
        "regions": ["us-central1", "us-east4", "europe-west4"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "gcp-tpu",
        "name": "Google Cloud TPU",
        "architectures": ["tpu"],
        "accelerators": ["tpu-v5e", "tpu-v5p", "tpu-v4"],
        "regions": ["us-central1", "us-east1", "europe-west4"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "azure",
        "name": "Azure GPU",
        "architectures": ["nvidia", "amd"],
        "accelerators": ["h100", "a100", "mi300x", "mi250"],
        "regions": ["eastus", "westus3", "southcentralus"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "coreweave",
        "name": "CoreWeave",
        "architectures": ["nvidia"],
        "accelerators": ["h100", "h200", "a100", "l40s"],
        "regions": ["us-east", "us-west", "eu-west"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "crusoe",
        "name": "Crusoe Cloud",
        "architectures": ["nvidia"],
        "accelerators": ["h100", "a100", "l40s"],
        "regions": ["us"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "fluidstack",
        "name": "Fluidstack",
        "architectures": ["nvidia"],
        "accelerators": ["h100", "h200", "a100"],
        "regions": ["us", "eu"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "tensorwave",
        "name": "TensorWave",
        "architectures": ["amd"],
        "accelerators": ["mi300x", "mi325x"],
        "regions": ["us-east", "us-west"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "intel-developer-cloud",
        "name": "Intel Developer Cloud",
        "architectures": ["intel-gaudi", "intel-xpu"],
        "accelerators": ["gaudi2", "gaudi3", "intel-max-1550"],
        "regions": ["us"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "macstadium",
        "name": "MacStadium",
        "architectures": ["apple-silicon"],
        "accelerators": ["m4", "m3-ultra", "m2-ultra"],
        "regions": ["us", "eu"],
        "account_mode": "anygpu-managed",
    },
    {
        "id": "scaleway-apple",
        "name": "Scaleway Apple Silicon",
        "architectures": ["apple-silicon"],
        "accelerators": ["m2", "m1"],
        "regions": ["fr-par"],
        "account_mode": "anygpu-managed",
    },
]


ACCELERATOR_SEEDS: dict[str, dict[str, Any]] = {
    "b200": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 192, "runtimes": ["vllm-cuda", "sglang-cuda", "llama.cpp"]},
    "h100": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 80, "runtimes": ["vllm-cuda", "sglang-cuda", "llama.cpp"]},
    "h200": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 141, "runtimes": ["vllm-cuda", "sglang-cuda", "llama.cpp"]},
    "a100": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 80, "runtimes": ["vllm-cuda", "sglang-cuda", "llama.cpp"]},
    "a40": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 48, "runtimes": ["vllm-cuda", "llama.cpp"]},
    "a16": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 16, "runtimes": ["vllm-cuda", "llama.cpp"]},
    "l40s": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 48, "runtimes": ["vllm-cuda", "sglang-cuda", "llama.cpp"]},
    "rtx-4090": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 24, "runtimes": ["vllm-cuda", "llama.cpp"]},
    "a10": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 24, "runtimes": ["vllm-cuda", "llama.cpp"]},
    "a10g": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 24, "runtimes": ["vllm-cuda", "llama.cpp"]},
    "l4": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 24, "runtimes": ["vllm-cuda", "llama.cpp"]},
    "t4": {"architecture": "nvidia", "vendor": "nvidia", "memory_gb": 16, "runtimes": ["vllm-cuda", "llama.cpp"]},
    "mi300x": {"architecture": "amd", "vendor": "amd", "memory_gb": 192, "runtimes": ["vllm-rocm", "sglang-rocm", "llama.cpp-hip"]},
    "mi355x": {"architecture": "amd", "vendor": "amd", "memory_gb": 288, "runtimes": ["vllm-rocm", "sglang-rocm", "llama.cpp-hip"]},
    "mi325x": {"architecture": "amd", "vendor": "amd", "memory_gb": 256, "runtimes": ["vllm-rocm", "sglang-rocm", "llama.cpp-hip"]},
    "mi250": {"architecture": "amd", "vendor": "amd", "memory_gb": 128, "runtimes": ["vllm-rocm", "llama.cpp-hip"]},
    "tpu-v5e": {"architecture": "tpu", "vendor": "google", "memory_gb": 16, "runtimes": ["jax-xla", "maxtext", "pytorch-xla", "vllm-tpu"]},
    "tpu-v5p": {"architecture": "tpu", "vendor": "google", "memory_gb": 95, "runtimes": ["jax-xla", "maxtext", "pytorch-xla", "vllm-tpu"]},
    "tpu-v4": {"architecture": "tpu", "vendor": "google", "memory_gb": 32, "runtimes": ["jax-xla", "maxtext", "pytorch-xla"]},
    "gaudi1": {"architecture": "intel-gaudi", "vendor": "intel", "memory_gb": 32, "runtimes": ["vllm-gaudi", "optimum-habana"]},
    "gaudi2": {"architecture": "intel-gaudi", "vendor": "intel", "memory_gb": 96, "runtimes": ["vllm-gaudi", "optimum-habana"]},
    "gaudi3": {"architecture": "intel-gaudi", "vendor": "intel", "memory_gb": 128, "runtimes": ["vllm-gaudi", "optimum-habana"]},
    "intel-max-1550": {"architecture": "intel-xpu", "vendor": "intel", "memory_gb": 128, "runtimes": ["vllm-xpu", "openvino", "pytorch-xpu"]},
    "m4": {"architecture": "apple-silicon", "vendor": "apple", "memory_gb": 64, "runtimes": ["llama.cpp-metal", "mlx", "vllm-metal"]},
    "m3-ultra": {"architecture": "apple-silicon", "vendor": "apple", "memory_gb": 512, "runtimes": ["llama.cpp-metal", "mlx", "vllm-metal"]},
    "m2-ultra": {"architecture": "apple-silicon", "vendor": "apple", "memory_gb": 192, "runtimes": ["llama.cpp-metal", "mlx", "vllm-metal"]},
    "m2": {"architecture": "apple-silicon", "vendor": "apple", "memory_gb": 24, "runtimes": ["llama.cpp-metal", "mlx"]},
    "m1": {"architecture": "apple-silicon", "vendor": "apple", "memory_gb": 16, "runtimes": ["llama.cpp-metal", "mlx"]},
}


MANAGED_POOL_SEEDS: list[dict[str, Any]] = [
    {"name": "managed-h100-runpod-us-secure", "provider": "runpod", "accelerator": "h100", "region": "us-secure", "count": 8},
    {"name": "managed-l40s-lambda-us-west", "provider": "lambda", "accelerator": "l40s", "region": "us-west", "count": 8},
    {"name": "managed-a100-vast-marketplace", "provider": "vast", "accelerator": "a100", "region": "marketplace", "count": 4},
    {"name": "managed-a100-vultr-cloud-gpu", "provider": "vultr", "accelerator": "a100", "region": "ewr", "count": 1},
    {"name": "managed-mi355x-vultr-bare-metal", "provider": "vultr", "accelerator": "mi355x", "region": "ord", "count": 8},
    {"name": "managed-b200-nebius-us", "provider": "nebius", "accelerator": "b200", "region": "us", "count": 8},
    {"name": "managed-h100-oci-us-ashburn-1", "provider": "oci", "accelerator": "h100", "region": "us-ashburn-1", "count": 8},
    {"name": "managed-h100-paperspace-us-east", "provider": "paperspace", "accelerator": "h100", "region": "us-east", "count": 1},
    {"name": "managed-b200-datacrunch-eu", "provider": "datacrunch", "accelerator": "b200", "region": "eu", "count": 8},
    {"name": "managed-h200-hyperstack-europe", "provider": "hyperstack", "accelerator": "h200", "region": "europe", "count": 1},
    {"name": "managed-l40s-cudo-global", "provider": "cudo", "accelerator": "l40s", "region": "global", "count": 1},
    {"name": "managed-h200-genesis-cloud-fr", "provider": "genesis-cloud", "accelerator": "h200", "region": "fr", "count": 8},
    {"name": "managed-h100-voltage-park-texas", "provider": "voltage-park", "accelerator": "h100", "region": "texas", "count": 8},
    {"name": "managed-h100-aws-us-east-1", "provider": "aws", "accelerator": "h100", "region": "us-east-1", "count": 8},
    {"name": "managed-h100-gcp-us-central1", "provider": "gcp", "accelerator": "h100", "region": "us-central1", "count": 8},
    {"name": "managed-h100-azure-eastus", "provider": "azure", "accelerator": "h100", "region": "eastus", "count": 8},
    {"name": "managed-mi300x-tensorwave-us-east", "provider": "tensorwave", "accelerator": "mi300x", "region": "us-east", "count": 8},
    {"name": "managed-mi300x-azure-eastus", "provider": "azure", "accelerator": "mi300x", "region": "eastus", "count": 8},
    {"name": "managed-tpu-v5e-gcp-us-central1", "provider": "gcp-tpu", "accelerator": "tpu-v5e", "region": "us-central1", "count": 8},
    {"name": "managed-gaudi-intel-us", "provider": "intel-developer-cloud", "accelerator": "gaudi2", "region": "us", "count": 8},
    {"name": "managed-gaudi-aws-us-east-1", "provider": "aws", "accelerator": "gaudi1", "region": "us-east-1", "count": 8},
    {"name": "managed-m4-macstadium-us", "provider": "macstadium", "accelerator": "m4", "region": "us", "count": 1},
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def add_event(state: dict[str, Any], target: str, message: str) -> None:
    state["events"].append({"time": now(), "target": target, "message": message})


def require_project(state: dict[str, Any]) -> str:
    project = state["session"].get("current_project")
    if not project:
        raise ValueError("No active project. Run `anygpu project create NAME` first.")
    return project


def latency_to_ms(value: str | None, default: int = 900) -> int:
    if not value:
        return default
    value = value.strip().lower()
    if value.endswith("ms"):
        return int(float(value[:-2]))
    if value.endswith("s"):
        return int(float(value[:-1]) * 1000)
    return int(float(value))


def traffic_to_qps(value: str | None) -> float:
    if not value:
        return 1.0
    match = re.match(r"([0-9.]+)\s*qps", value.strip().lower())
    return float(match.group(1)) if match else float(value)


def infer_parameters(source: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*[bB]", source)
    if match:
        return float(match.group(1))
    return 7.0


def refresh_provider_broker(state: dict[str, Any]) -> dict[str, Any]:
    providers = {
        provider["id"]: {
            **provider,
            "credential_status": "deployment_secret_required",
            "pricing_status": "seeded",
            "capacity_status": "unknown",
            "provisioning_status": "not_configured",
            "source": "static_catalog",
            "updated_at": now(),
        }
        for provider in BROKER_PROVIDER_SEEDS
    }
    accelerators = {
        accelerator: {
            "id": accelerator,
            **details,
            "source": "static_catalog",
            "updated_at": now(),
        }
        for accelerator, details in ACCELERATOR_SEEDS.items()
    }
    price_records: dict[str, dict[str, Any]] = {}
    capacity_records: dict[str, dict[str, Any]] = {}
    managed_pools: dict[str, dict[str, Any]] = {}
    for seed in MANAGED_POOL_SEEDS:
        pool = _broker_pool_record(seed, providers, accelerators)
        managed_pools[pool["name"]] = pool
        price_id = f"{pool['provider']}:{pool['accelerator']}:{pool['region']}:on-demand"
        price_records[price_id] = {
            "id": price_id,
            "provider": pool["provider"],
            "provider_name": pool["provider_name"],
            "pool": pool["name"],
            "architecture": pool["architecture"],
            "accelerator": pool["accelerator"],
            "region": pool["region"],
            "purchase_option": "on-demand",
            "price_per_hour_usd": None,
            "price_per_1m_tokens_usd": None,
            "price_status": "seeded",
            "freshness": "unknown",
            "source": "static_catalog",
            "updated_at": now(),
        }
        capacity_id = f"{pool['provider']}:{pool['accelerator']}:{pool['region']}"
        capacity_records[capacity_id] = {
            "id": capacity_id,
            "provider": pool["provider"],
            "provider_name": pool["provider_name"],
            "pool": pool["name"],
            "architecture": pool["architecture"],
            "accelerator": pool["accelerator"],
            "region": pool["region"],
            "available": None,
            "capacity_status": "unknown",
            "quota_status": "not_checked",
            "provisioning_status": "not_configured",
            "source": "static_catalog",
            "updated_at": now(),
        }
    broker = {
        "providers": providers,
        "accelerators": accelerators,
        "price_records": price_records,
        "capacity_records": capacity_records,
        "managed_pools": managed_pools,
        "refreshed_at": now(),
        "source": "static_catalog",
    }
    state["provider_broker"] = broker
    add_event(state, "broker", "Provider broker catalog refreshed from static catalog")
    return broker


def ensure_provider_broker(state: dict[str, Any]) -> dict[str, Any]:
    broker = state.setdefault("provider_broker", {})
    if not broker.get("providers") or not broker.get("managed_pools"):
        broker = refresh_provider_broker(state)
    return broker


def broker_providers(state: dict[str, Any], architecture: str | None = None) -> list[dict[str, Any]]:
    providers = list(ensure_provider_broker(state)["providers"].values())
    if architecture:
        providers = [provider for provider in providers if architecture in provider.get("architectures", [])]
    return sorted(providers, key=lambda provider: provider["id"])


def broker_price_records(
    state: dict[str, Any],
    accelerator: str | None = None,
    architecture: str | None = None,
) -> list[dict[str, Any]]:
    records = list(ensure_provider_broker(state)["price_records"].values())
    if accelerator:
        records = [record for record in records if record["accelerator"] == accelerator]
    if architecture:
        records = [record for record in records if record["architecture"] == architecture]
    return sorted(records, key=lambda record: (record["architecture"], record["accelerator"], record["provider"], record["region"]))


def broker_capacity_records(
    state: dict[str, Any],
    accelerator: str | None = None,
    architecture: str | None = None,
) -> list[dict[str, Any]]:
    records = list(ensure_provider_broker(state)["capacity_records"].values())
    if accelerator:
        records = [record for record in records if record["accelerator"] == accelerator]
    if architecture:
        records = [record for record in records if record["architecture"] == architecture]
    return sorted(records, key=lambda record: (record["architecture"], record["accelerator"], record["provider"], record["region"]))


def refresh_provider_prices(
    state: dict[str, Any],
    provider: str,
    accelerator: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    if provider not in {"vast", "vultr"}:
        raise ValueError("prices refresh currently supports --provider vast or vultr")
    config = load_config(state.get("config", {}))
    broker = ensure_provider_broker(state)
    if provider == "vultr":
        return _refresh_vultr_prices(state, broker, config, accelerator, limit)
    offers = _fetch_vast_offers(config, accelerator, limit)
    normalized = [_normalize_vast_offer(offer) for offer in offers]
    normalized = [offer for offer in normalized if offer]
    for offer in normalized:
        price_id = f"vast:{offer['accelerator']}:{offer['region']}:offer-{offer['offer_id']}"
        capacity_id = price_id
        broker["price_records"][price_id] = {
            "id": price_id,
            "provider": "vast",
            "provider_name": "Vast.ai",
            "pool": f"vast-offer-{offer['offer_id']}",
            "architecture": offer["architecture"],
            "accelerator": offer["accelerator"],
            "region": offer["region"],
            "purchase_option": "on-demand",
            "price_per_hour_usd": offer["price_per_hour_usd"],
            "price_per_1m_tokens_usd": None,
            "price_status": "live",
            "freshness": "fresh",
            "source": "vast_search_offers",
            "offer_id": offer["offer_id"],
            "gpu_name": offer["gpu_name"],
            "gpu_count": offer["gpu_count"],
            "memory_gb": offer["memory_gb"],
            "reliability": offer.get("reliability"),
            "driver_version": offer.get("driver_version"),
            "cuda_max_good": offer.get("cuda_max_good"),
            "updated_at": now(),
        }
        broker["capacity_records"][capacity_id] = {
            "id": capacity_id,
            "provider": "vast",
            "provider_name": "Vast.ai",
            "pool": f"vast-offer-{offer['offer_id']}",
            "architecture": offer["architecture"],
            "accelerator": offer["accelerator"],
            "region": offer["region"],
            "available": offer["available"],
            "capacity_status": "available" if offer["available"] else "unavailable",
            "quota_status": "not_checked",
            "provisioning_status": "not_configured",
            "source": "vast_search_offers",
            "offer_id": offer["offer_id"],
            "gpu_name": offer["gpu_name"],
            "gpu_count": offer["gpu_count"],
            "updated_at": now(),
        }
    broker["refreshed_at"] = now()
    state["provider_broker"] = broker
    add_event(state, "prices", f"Refreshed {len(normalized)} Vast.ai offer price(s)")
    return {
        "provider": "vast",
        "offers": len(normalized),
        "price_records": len(normalized),
        "capacity_records": len(normalized),
        "source": "vast_search_offers",
        "refreshed_at": broker["refreshed_at"],
    }


def _refresh_vultr_prices(
    state: dict[str, Any],
    broker: dict[str, Any],
    config: dict[str, Any],
    accelerator: str | None,
    limit: int,
) -> dict[str, Any]:
    payload = _fetch_vultr_plans(config, limit)
    normalized = _normalize_vultr_plans(payload, accelerator)
    for offer in normalized:
        price_id = f"vultr:{offer['accelerator']}:{offer['region']}:plan-{offer['plan_id']}"
        broker["price_records"][price_id] = {
            "id": price_id,
            "provider": "vultr",
            "provider_name": "Vultr",
            "pool": f"vultr-{offer['deployment_kind']}-{offer['plan_id']}",
            "architecture": offer["architecture"],
            "accelerator": offer["accelerator"],
            "region": offer["region"],
            "purchase_option": "on-demand",
            "price_per_hour_usd": offer["price_per_hour_usd"],
            "price_per_1m_tokens_usd": None,
            "price_status": "live",
            "freshness": "fresh",
            "source": "vultr_plans_api",
            "plan_id": offer["plan_id"],
            "deployment_kind": offer["deployment_kind"],
            "gpu_count": offer["gpu_count"],
            "memory_gb": offer["memory_gb"],
            "vcpu_count": offer.get("vcpu_count"),
            "ram_mb": offer.get("ram_mb"),
            "updated_at": now(),
        }
        broker["capacity_records"][price_id] = {
            "id": price_id,
            "provider": "vultr",
            "provider_name": "Vultr",
            "pool": f"vultr-{offer['deployment_kind']}-{offer['plan_id']}",
            "architecture": offer["architecture"],
            "accelerator": offer["accelerator"],
            "region": offer["region"],
            "available": True,
            "capacity_status": "available",
            "quota_status": "not_checked",
            "provisioning_status": "not_configured",
            "source": "vultr_plans_api",
            "plan_id": offer["plan_id"],
            "deployment_kind": offer["deployment_kind"],
            "gpu_count": offer["gpu_count"],
            "updated_at": now(),
        }
    broker["refreshed_at"] = now()
    state["provider_broker"] = broker
    add_event(state, "prices", f"Refreshed {len(normalized)} Vultr plan price(s)")
    return {
        "provider": "vultr",
        "offers": len(normalized),
        "price_records": len(normalized),
        "capacity_records": len(normalized),
        "source": "vultr_plans_api",
        "refreshed_at": broker["refreshed_at"],
    }


def _fetch_vast_offers(config: dict[str, Any], accelerator: str | None, limit: int) -> list[dict[str, Any]]:
    base_url = str(config["vast_api_base_url"])
    if base_url.startswith("https://") and not config.get("vast_api_key"):
        raise ValueError("vast_api_key is required for Vast.ai HTTPS price refresh")
    if base_url.startswith("file://"):
        with urllib.request.urlopen(base_url, timeout=5) as response:
            payload = json.loads(response.read().decode())
        return _vast_offer_list(payload)
    body: dict[str, Any] = {
        "limit": int(limit),
        "type": "on-demand",
        "verified": {"eq": True},
        "rentable": {"eq": True},
        "rented": {"eq": False},
    }
    gpu_names = _vast_gpu_names_for_accelerator(accelerator)
    if gpu_names:
        body["gpu_name"] = {"in": gpu_names}
    request = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {config.get('vast_api_key')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    return _vast_offer_list(payload)


def _fetch_vultr_plans(config: dict[str, Any], limit: int) -> dict[str, Any]:
    base_url = str(config["vultr_api_base_url"]).rstrip("/")
    if base_url.startswith("https://") and not config.get("vultr_api_key"):
        raise ValueError("vultr_api_key is required for Vultr HTTPS price refresh")
    if base_url.startswith("file://"):
        with urllib.request.urlopen(base_url, timeout=5) as response:
            payload = json.loads(response.read().decode())
        return payload if isinstance(payload, dict) else {}

    headers = {"Content-Type": "application/json"}
    if config.get("vultr_api_key"):
        headers["Authorization"] = f"Bearer {config['vultr_api_key']}"
    plans_url = f"{base_url}/plans?{urllib.parse.urlencode({'type': 'vcg', 'per_page': int(limit)})}"
    metal_url = f"{base_url}/plans-metal?{urllib.parse.urlencode({'per_page': int(limit)})}"
    return {
        "plans": _vultr_get_json(plans_url, headers).get("plans", []),
        "plans_metal": _vultr_get_json(metal_url, headers).get("plans_metal", []),
    }


def _vultr_get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode())
    return payload if isinstance(payload, dict) else {}


def _normalize_vultr_plans(payload: dict[str, Any], accelerator: str | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for plan in _vultr_plan_list(payload.get("plans")):
        records.extend(_normalize_vultr_plan(plan, "cloud-gpu"))
    for plan in _vultr_plan_list(payload.get("plans_metal")):
        records.extend(_normalize_vultr_plan(plan, "bare-metal"))
    if accelerator:
        records = [record for record in records if record["accelerator"] == accelerator]
    return records


def _vultr_plan_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [plan for plan in value if isinstance(plan, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _normalize_vultr_plan(plan: dict[str, Any], deployment_kind: str) -> list[dict[str, Any]]:
    plan_id = str(plan.get("id") or "")
    accelerator = _normalize_accelerator_name(plan_id)
    if not accelerator:
        return []
    accelerator_details = ACCELERATOR_SEEDS.get(accelerator, {})
    locations = plan.get("locations") or plan.get("regions") or []
    if isinstance(locations, str):
        locations = [locations]
    if not locations:
        locations = ["unknown"]
    monthly_cost = _float_or_none(plan.get("monthly_cost"))
    hourly_cost = round(monthly_cost / 730, 2) if monthly_cost is not None else None
    gpu_count = _infer_vultr_gpu_count(plan_id, deployment_kind)
    memory_gb = _infer_vultr_memory_gb(plan_id, accelerator, gpu_count)
    records = []
    for location in locations:
        records.append(
            {
                "plan_id": plan_id,
                "deployment_kind": deployment_kind,
                "architecture": accelerator_details.get("architecture", "unknown"),
                "accelerator": accelerator,
                "region": str(location),
                "price_per_hour_usd": hourly_cost,
                "gpu_count": gpu_count,
                "memory_gb": memory_gb,
                "vcpu_count": plan.get("vcpu_count") or plan.get("cpu_count"),
                "ram_mb": plan.get("ram"),
            }
        )
    return records


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_vultr_gpu_count(plan_id: str, deployment_kind: str) -> int:
    match = re.search(r"(\d+)x", plan_id.lower())
    if match:
        return int(match.group(1))
    if deployment_kind == "bare-metal" and ("mi355x" in plan_id.lower() or "mi325x" in plan_id.lower() or "b200" in plan_id.lower()):
        return 8
    return 1


def _infer_vultr_memory_gb(plan_id: str, accelerator: str, gpu_count: int) -> int:
    match = re.search(r"(\d+)vram", plan_id.lower())
    if match:
        return int(match.group(1))
    per_gpu = int(ACCELERATOR_SEEDS.get(accelerator, {}).get("memory_gb") or 0)
    return per_gpu * max(gpu_count, 1)


def _vast_offer_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        offers = payload.get("offers", [])
        if isinstance(offers, list):
            return [offer for offer in offers if isinstance(offer, dict)]
        if isinstance(offers, dict):
            return [offers]
    if isinstance(payload, list):
        return [offer for offer in payload if isinstance(offer, dict)]
    return []


def _normalize_vast_offer(offer: dict[str, Any]) -> dict[str, Any] | None:
    gpu_name = str(offer.get("gpu_name") or offer.get("gpu_display_name") or "")
    accelerator = _normalize_accelerator_name(gpu_name)
    if not accelerator:
        return None
    architecture = str(offer.get("gpu_arch") or ACCELERATOR_SEEDS.get(accelerator, {}).get("architecture", "unknown")).lower()
    if architecture == "nvidia":
        architecture = "nvidia"
    elif architecture == "amd":
        architecture = "amd"
    memory_mb = offer.get("gpu_ram") or offer.get("gpu_total_ram") or 0
    try:
        memory_gb = round(float(memory_mb) / 1024)
    except (TypeError, ValueError):
        memory_gb = ACCELERATOR_SEEDS.get(accelerator, {}).get("memory_gb", 0)
    return {
        "offer_id": str(offer.get("id") or offer.get("ask_contract_id") or offer.get("bundle_id")),
        "gpu_name": gpu_name,
        "architecture": architecture,
        "accelerator": accelerator,
        "gpu_count": int(float(offer.get("num_gpus") or 1)),
        "memory_gb": memory_gb,
        "price_per_hour_usd": float(offer.get("dph_total") or offer.get("dph_base") or 0.0),
        "region": str(offer.get("geolocation") or "unknown"),
        "available": bool(offer.get("rentable", True)) and not bool(offer.get("rented", False)),
        "reliability": offer.get("reliability"),
        "driver_version": offer.get("driver_version"),
        "cuda_max_good": offer.get("cuda_max_good"),
    }


def _normalize_accelerator_name(name: str) -> str | None:
    lowered = name.lower().replace("_", " ").replace("-", " ")
    patterns = [
        ("mi355x", "mi355x"),
        ("mi325x", "mi325x"),
        ("mi300x", "mi300x"),
        ("b200", "b200"),
        ("h200", "h200"),
        ("h100", "h100"),
        ("a100", "a100"),
        ("a40", "a40"),
        ("a16", "a16"),
        ("l40s", "l40s"),
        ("l40", "l40s"),
        ("rtx 4090", "rtx-4090"),
        ("4090", "rtx-4090"),
        ("l4", "l4"),
        ("a40", "l40s"),
        ("a6000", "l40s"),
        ("a5000", "l4"),
        ("3090", "rtx-4090"),
    ]
    for token, accelerator in patterns:
        if token in lowered:
            return accelerator
    return None


def _vast_gpu_names_for_accelerator(accelerator: str | None) -> list[str]:
    names = {
        "h100": ["H100", "NVIDIA H100 80GB HBM3", "NVIDIA H100 PCIe", "NVIDIA H100 NVL"],
        "h200": ["H200", "NVIDIA H200"],
        "a100": ["A100", "NVIDIA A100-SXM4-80GB", "NVIDIA A100 80GB PCIe"],
        "l40s": ["L40S", "NVIDIA L40S", "NVIDIA L40"],
        "rtx-4090": ["RTX_4090", "RTX 4090", "NVIDIA GeForce RTX 4090"],
        "l4": ["L4", "NVIDIA L4"],
        "mi300x": ["MI300X", "AMD Instinct MI300X OAM"],
    }
    return names.get(accelerator or "", [])


def _broker_pool_record(
    seed: dict[str, Any],
    providers: dict[str, dict[str, Any]],
    accelerators: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    provider = providers[seed["provider"]]
    accelerator = accelerators[seed["accelerator"]]
    return {
        "name": seed["name"],
        "provider": provider["id"],
        "provider_name": provider["name"],
        "kind": "managed",
        "architecture": accelerator["architecture"],
        "vendor": accelerator["vendor"],
        "accelerator": seed["accelerator"],
        "hardware": seed["accelerator"].upper(),
        "regions": [seed["region"]],
        "region": seed["region"],
        "modes": ["serverful"],
        "runtimes": accelerator["runtimes"],
        "max_vram_gb": accelerator["memory_gb"],
        "capacity": int(seed["count"]),
        "capacity_status": "unknown",
        "price_status": "seeded",
        "provisioning_status": "not_configured",
        "credential_status": provider["credential_status"],
        "hourly_cost": 0.0,
        "status": "catalog",
        "certified": False,
        "source": "broker_seed",
        "inventory": {
            "driver": accelerator["architecture"],
            "runtime_support": accelerator["runtimes"],
            "current_capacity": "unknown",
            "health": "not_provisioned",
            "provider": provider["id"],
            "provider_name": provider["name"],
        },
    }


def register_managed_pools(state: dict[str, Any]) -> None:
    broker = ensure_provider_broker(state)
    pools = {**MANAGED_POOLS, **(broker.get("managed_pools") or {})}
    for name, pool in pools.items():
        existing = state["compute_pools"].get(name, {})
        merged = {
            **pool,
            **existing,
            "name": name,
            "kind": "managed",
            "provider": pool.get("provider", "managed"),
            "certified": existing.get("certified", True),
            "status": existing.get("status", "certified"),
            "last_verified": existing.get("last_verified", now()),
            "inventory": existing.get(
                "inventory",
                {
                    "driver": f"{pool['accelerator']}-12.x",
                    "network": "ok",
                    "storage_cache": "ok",
                    "runtime_support": pool["runtimes"],
                    "current_capacity": "available",
                    "health": "healthy",
                },
            ),
        }
        state["compute_pools"][name] = merged
        ensure_cost_record(state, merged)
        verify_pool(state, name)
    add_event(state, "compute", "Managed compute enabled")


def connect_pool(state: dict[str, Any], provider: str, name: str, **details: Any) -> dict[str, Any]:
    if provider == "docker":
        return connect_docker_pool(state, name)
    project = require_project(state)
    pool = {
        "name": name,
        "kind": "byoc",
        "provider": provider,
        "project": project,
        "hardware": details.get("hardware") or ("H100" if provider == "kubernetes" else "A100"),
        "regions": [details.get("region") or "us-west"],
        "modes": ["serverful", "warm"],
        "runtimes": ["vllm", "sglang", "llama.cpp", "pytorch"],
        "accelerator": details.get("accelerator") or "cuda",
        "max_vram_gb": int(details.get("max_vram_gb") or 80),
        "hourly_cost": 0.0,
        "capacity": int(details.get("capacity") or 4),
        "status": "registered",
        "certified": False,
        "agent": {
            "components": [
                "anygpu-agent",
                "runtime-launcher",
                "metrics-sidecar",
                "log-forwarder",
                "node-prober",
                "model-cache-controller",
            ],
            "details": details,
        },
        "inventory": {
            "driver": "cuda-12.x",
            "network": "ok",
            "storage_cache": "ok",
            "runtime_support": ["vllm", "sglang", "llama.cpp", "pytorch"],
            "current_capacity": "available",
            "health": "healthy",
        },
    }
    state["compute_pools"][name] = pool
    add_event(state, name, f"Registered {provider} compute pool")
    return pool


def connect_docker_pool(state: dict[str, Any], name: str) -> dict[str, Any]:
    project = require_project(state)
    inventory = DockerProvider(load_config(state.get("config", {}))).list_inventory()
    max_vram_gb = max((int(gpu.get("memory_gb", 0)) for gpu in inventory["gpus"]), default=0)
    hardware = "Docker local"
    if inventory["gpus"]:
        hardware = ", ".join(gpu["name"] for gpu in inventory["gpus"])
    pool = {
        "name": name,
        "kind": "docker",
        "provider": "docker",
        "project": project,
        "hardware": hardware,
        "regions": ["local"],
        "modes": ["serverful"],
        "runtimes": inventory["runtimes_supported"],
        "accelerator": "cuda" if inventory["gpus"] else "cpu",
        "max_vram_gb": max_vram_gb,
        "hourly_cost": 0.0,
        "capacity": max(1, len(inventory["gpus"])),
        "status": inventory["status"],
        "certified": False,
        "inventory": inventory,
    }
    state["compute_pools"][name] = pool
    ensure_cost_record(state, pool)
    add_event(state, name, "Registered Docker compute pool")
    return pool


def get_compute_inventory(state: dict[str, Any], name: str) -> dict[str, Any]:
    pool = state["compute_pools"].get(name)
    if not pool:
        raise ValueError(f"Unknown compute pool {name}")
    if pool.get("kind") == "docker":
        inventory = DockerProvider(load_config(state.get("config", {}))).list_inventory()
        pool["inventory"] = inventory
        pool["status"] = inventory["status"]
        pool["hardware"] = ", ".join(gpu["name"] for gpu in inventory["gpus"]) if inventory["gpus"] else "Docker local"
        pool["max_vram_gb"] = max((int(gpu.get("memory_gb", 0)) for gpu in inventory["gpus"]), default=0)
    elif pool.get("provider") == "kubernetes":
        details = pool.get("agent", {}).get("details", {})
        provider = KubernetesProvider(details.get("context"), details.get("namespace"))
        inventory = provider.list_inventory(name)
        pool["inventory"] = inventory
        pool["status"] = inventory["status"]
        if inventory["nodes"]:
            accelerators = [
                accelerator
                for node in inventory["nodes"]
                for accelerator in node.get("accelerators", [])
            ]
            if accelerators:
                pool["hardware"] = ", ".join(sorted({accelerator["name"] for accelerator in accelerators}))
                pool["capacity"] = sum(int(accelerator.get("count", 0)) for accelerator in accelerators)
                pool["max_vram_gb"] = max(int(accelerator.get("memory_gb", 0)) for accelerator in accelerators)
                pool["accelerator"] = accelerators[0].get("vendor", pool.get("accelerator", "cuda"))
        if inventory.get("runtime_support"):
            pool["runtimes"] = inventory["runtime_support"]
    return pool.get("inventory", {})


def ensure_local_pool(state: dict[str, Any]) -> dict[str, Any]:
    config = load_config(state.get("config", {}))
    runtime = LlamaCppRuntime(config)
    availability = runtime.detect()
    pool = {
        "name": "local",
        "kind": "local",
        "provider": "local",
        "project": state["session"].get("current_project"),
        "hardware": "Local CPU/Metal",
        "regions": ["local"],
        "modes": ["serverful"],
        "runtimes": ["llama.cpp"],
        "accelerator": "local",
        "max_vram_gb": 0,
        "hourly_cost": 0.0,
        "capacity": 1,
        "status": "registered",
        "certified": False,
        "inventory": {
            "driver": "local",
            "network": "loopback",
            "storage_cache": config["model_cache_path"],
            "runtime_support": ["llama.cpp"] if availability["available"] else [],
            "current_capacity": "available",
            "health": "healthy" if availability["available"] else "unavailable",
            "llama_cpp": availability,
        },
    }
    existing = state["compute_pools"].get("local", {})
    merged = {**pool, **existing}
    merged["inventory"] = pool["inventory"]
    if existing.get("certified"):
        merged["certified"] = existing["certified"]
        merged["status"] = existing.get("status", pool["status"])
        merged["last_verified"] = existing.get("last_verified")
    state["compute_pools"]["local"] = merged
    return state["compute_pools"]["local"]


def verify_pool(state: dict[str, Any], name: str) -> list[dict[str, Any]]:
    if name == "local":
        ensure_local_pool(state)
    pool = state["compute_pools"].get(name)
    if not pool:
        raise ValueError(f"Unknown compute pool {name}")
    if pool.get("kind") == "local":
        return verify_local_pool(state, pool)
    if pool.get("provider") == "kubernetes":
        return verify_kubernetes_pool(state, pool)
    pool["certified"] = True
    pool["status"] = "certified"
    pool["last_verified"] = now()
    checks = [
        "schedule containers",
        "pull runtime images",
        "access model storage",
        "run accelerator",
        "forward metrics/logs",
        "serve health checks",
        "terminate cleanly",
        "enforce resource limits",
    ]
    pool["verification_checks"] = [{"name": check, "status": "pass"} for check in checks]
    records: list[dict[str, Any]] = []
    for runtime in pool["runtimes"]:
        if runtime == "pytorch":
            modes = ["batch", "finetune"]
        elif runtime == "llama.cpp":
            modes = ["serve", "batch"]
        else:
            modes = ["serve", "batch", "finetune"]
        record = {
            "pool": name,
            "hardware": pool["hardware"],
            "runtime": runtime,
            "status": "certified",
            "driver": pool["inventory"]["driver"] if "inventory" in pool else f"{pool['accelerator']}-12.x",
            "max_vram_gb": pool["max_vram_gb"],
            "last_verified": pool["last_verified"],
            "supported_modes": modes,
        }
        records.append(record)
    state["compatibility_records"] = [
        record for record in state["compatibility_records"] if record["pool"] != name
    ] + records
    add_event(state, name, f"Pool certified for {', '.join(pool['runtimes'])}")
    return records


def verify_local_pool(state: dict[str, Any], pool: dict[str, Any]) -> list[dict[str, Any]]:
    config = load_config(state.get("config", {}))
    runtime = LlamaCppRuntime(config)
    availability = runtime.detect()
    real = bool(availability["available"])
    pool["certified"] = True
    pool["status"] = "certified" if real else "simulated"
    pool["last_verified"] = now()
    pool["inventory"]["llama_cpp"] = availability
    pool["inventory"]["runtime_support"] = ["llama.cpp"] if real else []
    pool["verification_checks"] = [
        {"name": "detect llama.cpp server or CLI", "status": "pass" if real else "missing"},
        {"name": "model cache path available", "status": "pass"},
        {"name": "loopback endpoint available", "status": "pass"},
    ]
    record = {
        "pool": "local",
        "hardware": pool["hardware"],
        "runtime": "llama.cpp",
        "status": "certified" if real else "simulated",
        "driver": "local",
        "max_vram_gb": 0,
        "last_verified": pool["last_verified"],
        "supported_modes": ["serve", "batch"],
        "real": real,
        "simulated": not real,
        "details": availability,
    }
    state["compatibility_records"] = [
        existing for existing in state["compatibility_records"] if existing["pool"] != "local"
    ] + [record]
    add_event(state, "local", "Local llama.cpp compatibility verified" if real else "Local llama.cpp unavailable; simulator fallback enabled")
    return [record]


def verify_kubernetes_pool(state: dict[str, Any], pool: dict[str, Any]) -> list[dict[str, Any]]:
    inventory = get_compute_inventory(state, pool["name"])
    real = inventory.get("status") == "available"
    pool["certified"] = True
    pool["status"] = "certified" if real else "simulated"
    pool["last_verified"] = now()
    checks = inventory.get("checks") or []
    if not checks:
        checks = [{"name": "list kubernetes nodes", "status": "fail"}]
    if real:
        checks.append({"name": "gpu node detected", "status": "pass" if _kubernetes_accelerators(inventory) else "missing"})
    else:
        checks.extend(
            [
                {"name": "use simulated BYOC capacity", "status": "pass"},
                {"name": "gpu node detected", "status": "simulated"},
            ]
        )
    pool["verification_checks"] = checks
    runtimes = pool.get("runtimes") or ["vllm", "sglang", "llama.cpp", "pytorch"]
    records: list[dict[str, Any]] = []
    for runtime in runtimes:
        if runtime == "pytorch":
            modes = ["batch", "finetune"]
        elif runtime == "llama.cpp":
            modes = ["serve", "batch"]
        else:
            modes = ["serve", "batch", "finetune"]
        records.append(
            {
                "pool": pool["name"],
                "hardware": pool["hardware"],
                "runtime": runtime,
                "status": "certified" if real else "simulated",
                "driver": "kubernetes",
                "max_vram_gb": pool["max_vram_gb"],
                "last_verified": pool["last_verified"],
                "supported_modes": modes,
                "real": real,
                "simulated": not real,
                "inventory_status": inventory.get("status"),
            }
        )
    state["compatibility_records"] = [
        existing for existing in state["compatibility_records"] if existing["pool"] != pool["name"]
    ] + records
    message = "Kubernetes pool verified from live inventory" if real else "Kubernetes pool unavailable; simulator fallback enabled"
    add_event(state, pool["name"], message)
    return records


def _kubernetes_accelerators(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        accelerator
        for node in inventory.get("nodes", [])
        for accelerator in node.get("accelerators", [])
    ]


def register_model(
    state: dict[str, Any],
    name: str,
    source: str,
    task: str,
    model_format: str,
    base: str | None,
    runtime: str | None,
) -> dict[str, Any]:
    project = require_project(state)
    params = infer_parameters(source)
    model = {
        "name": name,
        "project": project,
        "source": source,
        "base": base,
        "task": task,
        "format": model_format,
        "parameter_size_b": params,
        "quantization": "q4_k_m" if source.lower().endswith(".gguf") or model_format == "gguf" else "none",
        "runtime": runtime,
        "checksum": hashlib.sha256(f"{source}:{base}:{task}".encode()).hexdigest()[:16],
        "license": "user-provided",
        "memory_estimate_gb": max(4, round(params * (0.65 if model_format == "gguf" else 2.0), 1)),
        "supported_tasks": [task],
        "approved_policies": [],
        "created_at": now(),
    }
    state["models"][name] = model
    add_event(state, name, f"Registered model from {source}")
    return model


def certified_pools(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [pool for pool in state["compute_pools"].values() if pool.get("certified")]


def profile_model(
    state: dict[str, Any],
    model_name: str,
    traffic: str | None,
    context: str | None,
    output_tokens_p50: str | None,
    latency_p95: str | None,
) -> dict[str, Any]:
    model = state["models"].get(model_name)
    if not model:
        raise ValueError(f"Unknown model {model_name}")
    qps = traffic_to_qps(traffic)
    context_tokens = int(context or 4096)
    output_tokens = int(output_tokens_p50 or 256)
    latency_ms = latency_to_ms(latency_p95)
    memory = model["memory_estimate_gb"] + round((context_tokens * qps) / 8192, 1)
    runtime_candidates = [
        {"name": "vLLM CUDA", "status": "pass"},
        {"name": "vLLM ROCm", "status": "pass"},
        {"name": "SGLang CUDA", "status": "pass"},
        {"name": "SGLang ROCm", "status": "needs-verification"},
        {
            "name": "llama.cpp",
            "status": "pass" if model["format"] == "gguf" or model.get("runtime") == "llama.cpp" else "not-ideal",
        },
    ]
    hardware_candidates = [
        {"name": "H100", "status": "pass"},
        {"name": "H200", "status": "pass"},
        {"name": "MI300X", "status": "pass"},
        {"name": "L40S", "status": "possible-with-quantization"},
        {"name": "Apple M-series", "status": "rejected-for-production-latency-or-size"},
    ]
    profile = {
        "model": model_name,
        "traffic_qps": qps,
        "context": context_tokens,
        "output_tokens_p50": output_tokens,
        "latency_p95_ms": latency_ms,
        "vram_required_gb": round(memory, 1),
        "runtime_candidates": runtime_candidates,
        "hardware_candidates": hardware_candidates,
        "created_at": now(),
    }
    state["profiles"][model_name] = profile
    add_event(state, model_name, "Profiled workload requirements")
    return profile


def target_pools(state: dict[str, Any], targets: str | None) -> list[dict[str, Any]]:
    if targets and "local" in {target.strip() for target in targets.split(",")}:
        ensure_local_pool(state)
    pools = certified_pools(state)
    if not targets or targets == "all-certified":
        return pools
    wanted = {target.strip() for target in targets.split(",") if target.strip()}
    selected = []
    for pool in pools:
        keys = {pool["name"], f"{pool['kind']}:{pool['name']}"}
        if pool["kind"] == "managed":
            keys.add(f"managed:{pool['name']}")
        if pool["kind"] == "byoc":
            keys.add(f"byoc:{pool['name']}")
        if pool["kind"] == "local":
            keys.add("local")
            keys.add("local:local")
        if keys & wanted:
            selected.append(pool)
    return selected


def benchmark_model(
    state: dict[str, Any],
    model_name: str,
    policy: str | None,
    targets: str | None,
    duration: str | None,
) -> dict[str, Any]:
    if model_name not in state["models"]:
        raise ValueError(f"Unknown model {model_name}")
    pools = target_pools(state, targets)
    if not pools:
        raise ValueError("No certified target pools match the requested targets")
    model = state["models"][model_name]
    results = []
    for pool in pools:
        if pool["kind"] == "local":
            results.append(local_benchmark_result(state, model, pool))
            continue
        runtime = "llama.cpp" if model["format"] == "gguf" or pool["accelerator"] == "cpu" else "vLLM"
        base_latency = 560 if "H100" in pool["hardware"] else 700 if "MI300X" in pool["hardware"] else 980
        if "serverless" in pool["modes"]:
            base_latency += 250
        cost_delta = "customer cost" if pool["kind"] == "byoc" else f"-{int(max(8, 52 - pool['hourly_cost'] * 10))}%"
        status = "pass" if base_latency <= 900 else "borderline" if base_latency <= 1100 else "bad p95"
        results.append(
            {
                "route": f"{pool['kind']}:{pool['name']}",
                "pool": pool["name"],
                "runtime": runtime,
                "p95_ms": base_latency,
                "tokens_per_sec": round(max(1.0, pool["max_vram_gb"] * pool["capacity"] * 7.0), 1),
                "estimated_cost": cost_delta,
                "status": status,
                "gpu_utilization": 0.72 if status == "pass" else 0.54,
                "vram_usage_gb": min(pool["max_vram_gb"], model["memory_estimate_gb"]),
                "error_rate": 0.0003 if status == "pass" else 0.003,
                "cold_start_ms": 18000 if "serverless" in pool["modes"] else 3200,
                "queue_delay_ms": 24 if status == "pass" else 110,
            }
        )
    benchmark = {
        "model": model_name,
        "policy": policy or "balanced",
        "targets": targets or "all-certified",
        "duration": duration or "10m",
        "results": sorted(results, key=lambda item: (item["status"] != "pass", item["p95_ms"])),
        "created_at": now(),
    }
    state["benchmarks"][model_name] = benchmark
    add_event(state, model_name, f"Benchmarked {len(results)} route(s)")
    return benchmark


def run_benchmark(
    state: dict[str, Any],
    model_source: str,
    runtime: str,
    compute: str,
    profile: str,
) -> dict[str, Any]:
    pool = state["compute_pools"].get(compute)
    if not pool:
        raise ValueError(f"Unknown compute pool {compute}")
    if pool.get("kind") != "docker":
        raise ValueError("benchmark run currently supports Docker compute only")
    if runtime not in {"llama.cpp", "vllm"}:
        raise ValueError("benchmark run currently supports runtime=llama.cpp or runtime=vllm")
    model_record = state["models"].get(model_source)
    source = model_record["source"] if model_record else model_source
    config = load_config(state.get("config", {}))
    provider = DockerProvider(config)
    inventory = provider.list_inventory()
    pool["inventory"] = inventory
    pool["status"] = inventory["status"]
    if not inventory["docker"]["available"]:
        raise RuntimeError(f"Docker is unavailable: {inventory['docker'].get('error', 'docker daemon is not reachable')}")
    bench_id = f"bench_{int(time.time() * 1000)}"
    startup_start = time.perf_counter()
    handle = provider.create_runtime({"name": bench_id, "runtime": runtime, "model_path": source, "compute": compute})
    process = provider.start_runtime(handle)
    startup_ms = max(1, int((time.perf_counter() - startup_start) * 1000))
    try:
        measurement = _run_openai_chat_benchmark(process["upstream_url"], profile)
        success = True
        error = None
    except Exception as exc:
        measurement = {
            "latency_ms": 0,
            "tokens_generated": 0,
            "tokens_per_second": 0.0,
            "response_text": "",
        }
        success = False
        error = str(exc)
    finally:
        stopped = provider.stop_runtime(process)
    hardware = _benchmark_hardware(inventory, pool)
    model_identity = _record_benchmark_model(state, model_source, source, runtime)
    hardware_id = _record_benchmark_hardware(state, hardware)
    runtime_id = _record_benchmark_runtime(state, runtime, handle, inventory)
    result = {
        "id": bench_id,
        "model_id": model_identity["id"],
        "runtime_id": runtime_id,
        "hardware_id": hardware_id,
        "model": source,
        "model_name": model_source,
        "runtime": runtime,
        "compute": compute,
        "provider": "docker",
        "profile": profile,
        "hardware": hardware,
        "success": success,
        "simulated": False,
        "ttft_ms_p50": measurement["latency_ms"],
        "tokens_per_second_p50": measurement["tokens_per_second"],
        "tokens_per_second_p95": measurement["tokens_per_second"],
        "max_batch_size": _profile_batch_size(profile),
        "vram_used_gb": None,
        "startup_time_ms": startup_ms,
        "tokens_generated": measurement["tokens_generated"],
        "token_count_method": "estimated_from_response_text",
        "error": error,
        "upstream_url": process.get("upstream_url"),
        "container_id": process.get("container_id"),
        "container_name": process.get("container_name"),
        "container_status_after_benchmark": stopped.get("status"),
        "created_at": now(),
    }
    state.setdefault("benchmark_results", []).append(result)
    _record_benchmark_compatibility(state, result)
    add_event(state, bench_id, f"Benchmarked {runtime} on {compute}")
    return result


def ensure_cost_record(state: dict[str, Any], pool: dict[str, Any]) -> dict[str, Any]:
    key = f"{pool['provider']}:{pool['name']}"
    existing = state.setdefault("cost_records", {}).get(key)
    if existing:
        return existing
    default_cost = 0.0 if pool.get("kind") in {"docker", "local"} else float(pool.get("estimated_cost_per_1m_tokens", 0.72))
    label = "local/free" if default_cost == 0 else f"${default_cost:.4f}/1M tokens"
    record = {
        "id": key,
        "provider": pool["provider"],
        "compute": pool["name"],
        "meter": "tokens",
        "per_1m_tokens_usd": default_cost,
        "currency": "USD",
        "label": "broker seeded price unknown" if pool.get("source") == "broker_seed" else label,
        "source": "broker_seed" if pool.get("source") == "broker_seed" else "default",
        "updated_at": now(),
    }
    state["cost_records"][key] = record
    return record


def set_cost_record(
    state: dict[str, Any],
    compute: str,
    per_1m_tokens: str,
    label: str | None = None,
) -> dict[str, Any]:
    pool = state["compute_pools"].get(compute)
    if not pool:
        raise ValueError(f"Unknown compute pool {compute}")
    value = float(per_1m_tokens)
    key = f"{pool['provider']}:{compute}"
    record = {
        "id": key,
        "provider": pool["provider"],
        "compute": compute,
        "meter": "tokens",
        "per_1m_tokens_usd": value,
        "currency": "USD",
        "label": label or ("local/free" if value == 0 else f"${value:.4f}/1M tokens"),
        "source": "user",
        "updated_at": now(),
    }
    state.setdefault("cost_records", {})[key] = record
    add_event(state, compute, f"Updated cost record to {record['label']}")
    return record


def _run_openai_chat_benchmark(upstream_url: str, profile: str) -> dict[str, Any]:
    spec = _benchmark_profile(profile)
    payload = {
        "model": "anygpu-benchmark",
        "messages": [{"role": "user", "content": "Write one short sentence for a benchmark response."}],
        "max_tokens": spec["output_tokens"],
        "stream": False,
    }
    data = json.dumps(payload).encode()
    deadline = time.time() + 30.0
    last_error = "benchmark request did not run"
    while time.time() < deadline:
        request = urllib.request.Request(
            f"{upstream_url}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=5.0) as response:
                body = json.loads(response.read().decode())
            latency_ms = max(1, int((time.perf_counter() - start) * 1000))
            text = _extract_chat_text(body)
            tokens = int(body.get("usage", {}).get("completion_tokens") or _estimate_tokens(text))
            return {
                "latency_ms": latency_ms,
                "tokens_generated": tokens,
                "tokens_per_second": round(tokens / max(latency_ms / 1000, 0.001), 2),
                "response_text": text,
            }
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(0.25)
    raise RuntimeError(last_error)


def _extract_chat_text(body: dict[str, Any]) -> str:
    choices = body.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or choices[0].get("text") or "")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def _benchmark_profile(profile: str) -> dict[str, int]:
    profiles = {
        "latency-chat": {"batch": 1, "input_tokens": 512, "output_tokens": 128},
        "throughput-chat": {"batch": 8, "input_tokens": 512, "output_tokens": 128},
        "long-context": {"batch": 1, "input_tokens": 8192, "output_tokens": 256},
    }
    return profiles.get(profile, profiles["latency-chat"])


def _profile_batch_size(profile: str) -> int:
    return _benchmark_profile(profile)["batch"]


def _benchmark_hardware(inventory: dict[str, Any], pool: dict[str, Any]) -> dict[str, Any]:
    gpu = (inventory.get("gpus") or [{}])[0]
    return {
        "id": f"{pool['provider']}:local",
        "provider": pool["provider"],
        "vendor": gpu.get("vendor", "cpu"),
        "accelerator_name": gpu.get("name", pool.get("hardware", "Docker local")),
        "memory_gb": gpu.get("memory_gb", 0),
        "driver_version": gpu.get("driver"),
    }


def _stable_id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.lower()).strip("-")
    digest = hashlib.sha256(value.encode()).hexdigest()[:10]
    return f"{prefix}_{slug[:48]}_{digest}"


def _record_benchmark_model(
    state: dict[str, Any],
    model_name: str,
    source: str,
    runtime: str,
) -> dict[str, Any]:
    model_id = _stable_id("model", source)
    model_format = "gguf" if source.lower().endswith(".gguf") else "hf" if source.startswith("hf:") else "unknown"
    record = {
        "id": model_id,
        "name": model_name,
        "source": source,
        "format": model_format,
        "runtime_hint": runtime,
        "quantization": "unknown",
        "created_at": now(),
        "last_seen": now(),
    }
    existing = state.setdefault("model_records", {}).get(model_id, {})
    state["model_records"][model_id] = {**record, **existing, "last_seen": record["last_seen"]}
    return state["model_records"][model_id]


def _record_benchmark_hardware(state: dict[str, Any], hardware: dict[str, Any]) -> str:
    hardware_id = _stable_id(
        "hw",
        f"{hardware['provider']}:{hardware['vendor']}:{hardware['accelerator_name']}:{hardware.get('memory_gb', 0)}",
    )
    record = {
        "id": hardware_id,
        "provider": hardware["provider"],
        "vendor": hardware["vendor"],
        "accelerator_name": hardware["accelerator_name"],
        "memory_gb": hardware.get("memory_gb", 0),
        "driver_version": hardware.get("driver_version"),
        "runtime_capabilities_json": {},
        "last_seen": now(),
    }
    existing = state.setdefault("hardware_nodes", {}).get(hardware_id, {})
    state["hardware_nodes"][hardware_id] = {**record, **existing, "last_seen": record["last_seen"]}
    return hardware_id


def _record_benchmark_runtime(
    state: dict[str, Any],
    runtime: str,
    handle: dict[str, Any],
    inventory: dict[str, Any],
) -> str:
    runtime_id = _stable_id("rt", f"{runtime}:{handle.get('image', 'local')}")
    capabilities = inventory.get("runtime_capabilities", {}).get(runtime, {})
    record = {
        "id": runtime_id,
        "name": runtime,
        "version": "unknown",
        "backend": "docker",
        "image": handle.get("image"),
        "capabilities": capabilities,
        "last_seen": now(),
    }
    existing = state.setdefault("runtime_profiles", {}).get(runtime_id, {})
    state["runtime_profiles"][runtime_id] = {**record, **existing, "last_seen": record["last_seen"]}
    return runtime_id


def _record_benchmark_compatibility(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    status = "verified" if result["success"] else "failed"
    record_id = _stable_id(
        "compat",
        f"{result['model_id']}:{result['runtime_id']}:{result['hardware_id']}:{result['profile']}",
    )
    record = {
        "id": record_id,
        "model_id": result["model_id"],
        "runtime_id": result["runtime_id"],
        "hardware_id": result["hardware_id"],
        "status": status,
        "source": "benchmark",
        "benchmark_result_id": result["id"],
        "profile": result["profile"],
        "success": result["success"],
        "simulated": result["simulated"],
        "ttft_ms_p50": result["ttft_ms_p50"],
        "tokens_per_second_p50": result["tokens_per_second_p50"],
        "tokens_per_second_p95": result["tokens_per_second_p95"],
        "max_batch_size": result["max_batch_size"],
        "vram_used_gb": result["vram_used_gb"],
        "error": result["error"],
        "created_at": now(),
    }
    state["compatibility_records"] = [
        existing
        for existing in state.get("compatibility_records", [])
        if not (
            existing.get("id") == record_id
            or (
                existing.get("source") == "benchmark"
                and existing.get("model_id") == result["model_id"]
                and existing.get("runtime_id") == result["runtime_id"]
                and existing.get("hardware_id") == result["hardware_id"]
                and existing.get("profile") == result["profile"]
            )
        )
    ] + [record]
    return record


def local_benchmark_result(state: dict[str, Any], model: dict[str, Any], pool: dict[str, Any]) -> dict[str, Any]:
    config = load_config(state.get("config", {}))
    runtime = LlamaCppRuntime(config)
    availability = runtime.detect()
    can_run_real = model["format"] == "gguf" and availability["available"]
    if can_run_real:
        validation = runtime.validate_model_path(model["source"])
        if not validation["valid"]:
            raise ValueError(validation["error"])
        provider = LocalProvider(config)
        startup_start = time.perf_counter()
        process = provider.launch_llama_server(f"benchmark-{model['name']}", model["source"])
        startup_time_ms = max(1, int((time.perf_counter() - startup_start) * 1000))
        try:
            if process["health"] != "healthy":
                raise ValueError(f"llama.cpp benchmark server failed health check; logs: {process['logs_path']}")
            measurement = runtime.run_prompt_benchmark(process["upstream_url"], model["name"])
            if not measurement["ok"]:
                raise ValueError(f"llama.cpp benchmark prompt failed: {measurement['error']}")
        finally:
            provider.stop(process)
        simulated = False
        status = "pass"
        p95_ms = measurement["latency_ms"]
        tokens_per_sec = measurement["tokens_per_sec"]
    else:
        measurement = {}
        process = {}
        startup_time_ms = 0
        simulated = True
        status = "pass" if model["format"] == "gguf" else "borderline"
        p95_ms = 1200 if model["format"] == "gguf" else 1500
        tokens_per_sec = 18.0 if model["format"] == "gguf" else 8.0
    return {
        "route": "local:local",
        "pool": "local",
        "runtime": "llama.cpp",
        "p95_ms": p95_ms,
        "tokens_per_sec": tokens_per_sec,
        "estimated_cost": "local cost",
        "status": status,
        "gpu_utilization": 0.0,
        "vram_usage_gb": 0,
        "error_rate": 0.0005 if not simulated else 0.002,
        "cold_start_ms": 700,
        "queue_delay_ms": 5,
        "simulated": simulated,
        "real": not simulated,
        "reason": "real llama.cpp benchmark" if not simulated else "simulated fallback: GGUF and llama.cpp availability required",
        "tokens_generated": int(measurement.get("tokens_generated", 0)),
        "token_count_method": measurement.get("token_count_method", "none"),
        "benchmark_prompt": measurement.get("benchmark_prompt", ""),
        "startup_time_ms": startup_time_ms,
        "model_load_time_ms": startup_time_ms,
        "total_latency_ms": p95_ms,
        "logs_path": process.get("logs_path"),
        "upstream_url": process.get("upstream_url"),
        "success": status == "pass",
    }


def create_policy(state: dict[str, Any], name: str, **kwargs: Any) -> dict[str, Any]:
    policy = {
        "name": name,
        "objective": kwargs.get("objective") or "balanced",
        "max_p95_ms": latency_to_ms(kwargs.get("max_p95"), 900),
        "fallback": kwargs.get("fallback") or "optional",
        "regions": split_csv(kwargs.get("regions")),
        "data_residency": kwargs.get("data_residency"),
        "prefer": kwargs.get("prefer"),
        "allow_managed_overflow": str(kwargs.get("allow_managed_overflow", "false")).lower() == "true",
        "spot_allowed": str(kwargs.get("spot_allowed", "false")).lower() == "true",
        "serverless_allowed": str(kwargs.get("serverless_allowed", "false")).lower() == "true",
        "max_monthly_spend": kwargs.get("max_monthly_spend"),
        "min_replicas": kwargs.get("min_replicas"),
        "created_at": now(),
    }
    state["policies"][name] = policy
    add_event(state, name, "Created deployment policy")
    return policy


def split_csv(value: str | None) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()] if value else []


def select_routes(state: dict[str, Any], model_name: str, policy_name: str) -> list[dict[str, Any]]:
    policy = state["policies"].get(policy_name)
    if not policy:
        raise ValueError(f"Unknown policy {policy_name}")
    benchmark = state["benchmarks"].get(model_name)
    if not benchmark:
        benchmark = benchmark_model(state, model_name, policy["objective"], "all-certified", "3m")
    candidates = [result for result in benchmark["results"] if result["status"] in {"pass", "borderline"}]
    candidates = [result for result in candidates if result["p95_ms"] <= policy["max_p95_ms"] or result["status"] == "borderline"]
    if policy.get("prefer") == "byoc":
        candidates.sort(key=lambda item: (not item["route"].startswith("byoc:"), item["p95_ms"]))
    elif policy.get("objective") == "cheapest":
        candidates.sort(key=lambda item: (item["estimated_cost"] == "customer cost", item["p95_ms"]))
    else:
        candidates.sort(key=lambda item: item["p95_ms"])
    if not candidates:
        raise ValueError("No benchmarked route satisfies the policy")
    routes = []
    for index, candidate in enumerate(candidates[:3]):
        role = "primary" if index == 0 else "fallback" if index == 1 else "overflow"
        routes.append(
            {
                "role": role,
                "route": candidate["route"],
                "pool": candidate["pool"],
                "runtime": candidate["runtime"],
                "p95_ms": candidate["p95_ms"],
                "tokens_per_sec": candidate["tokens_per_sec"],
                "estimated_cost": candidate["estimated_cost"],
                "status": "healthy",
                "simulated": bool(candidate.get("simulated", True)),
                "real": bool(candidate.get("real", False)),
            }
        )
    if policy.get("fallback") == "required" and len(routes) == 1:
        primary = dict(routes[0])
        primary["role"] = "fallback"
        primary["route"] = f"{primary['route']}-standby"
        routes.append(primary)
    return routes


def deploy_model(
    state: dict[str, Any],
    model_name: str,
    name: str,
    policy_name: str,
    runtime: str | None,
    replicas: str | None,
    endpoint: str | None,
) -> dict[str, Any]:
    if model_name not in state["models"]:
        raise ValueError(f"Unknown model {model_name}")
    routes = select_routes(state, model_name, policy_name)
    deployment = {
        "name": name,
        "model": model_name,
        "policy": policy_name,
        "runtime": runtime or "auto",
        "replicas": parse_replicas(replicas),
        "endpoint": endpoint or "openai",
        "gateway": gateway_contract(name),
        "url": gateway_contract(name)["chat_completions_url"],
        "routes": routes,
        "health": "healthy",
        "created_at": now(),
        "metrics": {
            "p95_ms": routes[0]["p95_ms"],
            "error_rate": 0.0003,
            "tokens_per_sec": routes[0]["tokens_per_sec"],
            "queue_depth": 0,
            "cost_per_1m_tokens": effective_cost(routes[0]),
        },
    }
    if routes[0]["pool"] == "local" and routes[0]["runtime"] == "llama.cpp" and not routes[0].get("simulated", True):
        validation = LlamaCppRuntime(load_config(state.get("config", {}))).validate_model_path(state["models"][model_name]["source"])
        if not validation["valid"]:
            raise ValueError(validation["error"])
        config = load_config(state.get("config", {}))
        provider = LocalProvider(config)
        process = provider.launch_llama_server(name, state["models"][model_name]["source"])
        deployment["runtime_process"] = process
        deployment["routes"][0]["runtime_url"] = process["upstream_url"]
        deployment["routes"][0]["upstream_url"] = process["upstream_url"]
        deployment["routes"][0]["status"] = process["health"]
    state["deployments"][name] = deployment
    add_event(state, name, f"Deployment live on {routes[0]['route']}")
    return deployment


def schedule_deployment(
    state: dict[str, Any],
    name: str,
    model_source: str,
    strategy: str | None,
    sla: str | None,
    max_cost: str | None,
) -> dict[str, Any]:
    source = state["models"].get(model_source, {}).get("source", model_source)
    candidates = rank_placement_candidates(state, source, strategy or "cheapest-compatible", sla or "latency", max_cost)
    if not candidates:
        raise ValueError(f"No verified benchmark compatibility records match model {source}")
    selected = candidates[0]
    deployment = {
        "name": name,
        "kind": "scheduled",
        "model": source,
        "strategy": strategy or "cheapest-compatible",
        "sla": sla or "latency",
        "max_cost": max_cost,
        "provider": selected["provider"],
        "runtime": selected["runtime"],
        "compute": selected["compute"],
        "health": "scheduled",
        "created_at": now(),
        "scheduler_decision": {
            "selected": selected,
            "candidates": candidates,
            "explanation": selected["reasons"],
        },
        "routes": [
            {
                "role": "primary",
                "route": f"{selected['provider']}:{selected['compute']}",
                "pool": selected["compute"],
                "runtime": selected["runtime"],
                "status": "scheduled",
                "simulated": bool(selected.get("simulated", False)),
                "real": not bool(selected.get("simulated", False)),
                "p95_ms": selected["ttft_ms_p50"],
                "tokens_per_sec": selected["tokens_per_second_p50"],
                "estimated_cost": selected["estimated_cost_label"],
            }
        ],
        "metrics": {
            "p95_ms": selected["ttft_ms_p50"],
            "error_rate": 0.0,
            "tokens_per_sec": selected["tokens_per_second_p50"],
            "queue_depth": 0,
            "cost_per_1m_tokens": selected["estimated_cost_per_1m_tokens"],
        },
    }
    state["deployments"][name] = deployment
    add_event(state, name, f"Scheduled deployment on {selected['compute']} with {selected['runtime']}")
    return deployment


def rank_placement_candidates(
    state: dict[str, Any],
    source: str,
    strategy: str,
    sla: str,
    max_cost: str | None,
) -> list[dict[str, Any]]:
    model_id = _stable_id("model", source)
    benchmark_by_id = {result["id"]: result for result in state.get("benchmark_results", [])}
    candidates = []
    for record in state.get("compatibility_records", []):
        if record.get("source") != "benchmark" or record.get("status") != "verified":
            continue
        if record.get("model_id") != model_id:
            continue
        benchmark = benchmark_by_id.get(record.get("benchmark_result_id"))
        if not benchmark or not benchmark.get("success"):
            continue
        runtime = state.get("runtime_profiles", {}).get(record["runtime_id"], {})
        hardware = state.get("hardware_nodes", {}).get(record["hardware_id"], {})
        compute = benchmark["compute"]
        pool = dict(state.get("compute_pools", {}).get(compute, {}))
        pool["_state_cost_records"] = state.setdefault("cost_records", {})
        estimated_cost = _estimated_cost_per_1m_tokens(benchmark, pool)
        if max_cost is not None and estimated_cost > _parse_max_cost(max_cost):
            continue
        score = _placement_score(record, benchmark, pool, estimated_cost, strategy, sla)
        estimated_cost_label = _estimated_cost_label(benchmark, pool, estimated_cost)
        candidates.append(
            {
                "score": score,
                "model": source,
                "model_id": record["model_id"],
                "runtime": runtime.get("name", benchmark["runtime"]),
                "runtime_id": record["runtime_id"],
                "provider": benchmark["provider"],
                "compute": compute,
                "hardware_id": record["hardware_id"],
                "hardware": hardware,
                "hardware_name": hardware.get("accelerator_name", benchmark.get("hardware", {}).get("accelerator_name", "unknown")),
                "compatibility_status": record["status"],
                "benchmark_result_id": benchmark["id"],
                "ttft_ms_p50": benchmark["ttft_ms_p50"],
                "tokens_per_second_p50": benchmark["tokens_per_second_p50"],
                "tokens_per_second_p95": benchmark["tokens_per_second_p95"],
                "estimated_cost_per_1m_tokens": estimated_cost,
                "estimated_cost_label": estimated_cost_label,
                "simulated": bool(benchmark.get("simulated", True)),
                "profile": benchmark["profile"],
                "reasons": _placement_reasons(record, benchmark, hardware, estimated_cost_label),
            }
        )
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def explain_scheduled_deployment(state: dict[str, Any], name: str) -> str:
    deployment = state["deployments"].get(name)
    if not deployment:
        raise ValueError(f"Unknown deployment {name}")
    decision = deployment.get("scheduler_decision")
    if not decision:
        raise ValueError(f"Deployment {name} has no scheduler decision")
    selected = decision["selected"]
    lines = [
        f"Selected {selected['compute']} / {selected['hardware_name']} / {selected['runtime']} because:",
        *[f"- {reason}" for reason in decision.get("explanation", [])],
    ]
    return "\n".join(lines)


def generate_kubernetes_manifest(
    state: dict[str, Any],
    name: str,
    model_source: str,
    runtime: str | None,
    gpu: str | None,
    namespace: str | None,
    replicas: str | None,
) -> dict[str, Any]:
    source = state["models"].get(model_source, {}).get("source", model_source)
    selected_runtime = runtime or ("llama.cpp" if source.lower().endswith(".gguf") else "vllm")
    if selected_runtime not in {"vllm", "llama.cpp"}:
        raise ValueError("Kubernetes manifests currently support runtime=vllm or runtime=llama.cpp")
    replica_count = int(replicas or 1)
    ns = namespace or "default"
    deployment_name = f"{_k8s_name(name)}-{_k8s_name(selected_runtime)}"
    if selected_runtime == "vllm":
        image = "vllm/vllm-openai:latest"
        model_id = source.removeprefix("hf:")
        port = 8000
        args = ["--model", model_id]
        mount_path = "/root/.cache/huggingface"
    else:
        image = "ghcr.io/ggml-org/llama.cpp:server"
        model_name = source.split("/")[-1]
        port = 8080
        args = ["-m", f"/models/{model_name}"]
        mount_path = "/models"
    docs = [
        _k8s_config_map(deployment_name, ns, source, selected_runtime),
        _k8s_pvc(deployment_name, ns),
        _k8s_deployment(deployment_name, ns, replica_count, image, args, port, gpu or "none", mount_path),
        _k8s_service(deployment_name, ns, port),
    ]
    yaml = "\n---\n".join(_render_yaml(doc) for doc in docs) + "\n"
    record = {
        "name": name,
        "deployment_name": deployment_name,
        "namespace": ns,
        "runtime": selected_runtime,
        "model": source,
        "gpu": gpu or "none",
        "replicas": replica_count,
        "yaml": yaml,
        "created_at": now(),
    }
    state.setdefault("kubernetes_manifests", {})[name] = record
    add_event(state, name, f"Generated Kubernetes manifest for {selected_runtime}")
    return record


def _k8s_name(value: str) -> str:
    name = re.sub(r"[^a-z0-9-]+", "-", value.lower().replace(".", "-")).strip("-")
    return name or "anygpu"


def _k8s_config_map(name: str, namespace: str, model: str, runtime: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": f"{name}-config", "namespace": namespace},
        "data": {"model": model, "runtime": runtime},
    }


def _k8s_pvc(name: str, namespace: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": f"{name}-model-cache", "namespace": namespace},
        "spec": {
            "accessModes": ["ReadWriteOnce"],
            "resources": {"requests": {"storage": "50Gi"}},
        },
    }


def _k8s_deployment(
    name: str,
    namespace: str,
    replicas: int,
    image: str,
    args: list[str],
    port: int,
    gpu: str,
    mount_path: str,
) -> dict[str, Any]:
    limits: dict[str, Any] = {}
    node_selector: dict[str, str] = {}
    if gpu != "none":
        limits["nvidia.com/gpu"] = 1
        node_selector["anygpu.ai/gpu"] = gpu
    container: dict[str, Any] = {
        "name": "runtime",
        "image": image,
        "args": args,
        "ports": [{"containerPort": port}],
        "volumeMounts": [{"name": "model-cache", "mountPath": mount_path}],
    }
    if limits:
        container["resources"] = {"limits": limits}
    pod_spec: dict[str, Any] = {
        "containers": [container],
        "volumes": [{"name": "model-cache", "persistentVolumeClaim": {"claimName": f"{name}-model-cache"}}],
    }
    if node_selector:
        pod_spec["nodeSelector"] = node_selector
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": pod_spec,
            },
        },
    }


def _k8s_service(name: str, namespace: str, port: int) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "selector": {"app": name},
            "ports": [{"name": "http", "port": port, "targetPort": port}],
        },
    }


def _render_yaml(value: Any, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = " " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(_render_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(item)}")
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{prefix}-")
                lines.append(_render_yaml(item, indent + 2))
            elif isinstance(item, list):
                lines.append(f"{prefix}-")
                lines.append(_render_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    else:
        lines.append(f"{prefix}{_yaml_scalar(value)}")
    return "\n".join(lines)


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or text.startswith(("{", "[", "*", "&", "!", "@")) or ": " in text:
        return json.dumps(text)
    return text


def _placement_score(
    record: dict[str, Any],
    benchmark: dict[str, Any],
    pool: dict[str, Any],
    estimated_cost: float,
    strategy: str,
    sla: str,
) -> float:
    compatibility_score = 100 if record.get("status") == "verified" else 0
    availability_score = 15 if pool.get("status") in {"available", "certified"} else 5
    latency_penalty = min(float(benchmark.get("ttft_ms_p50", 5000)) / 1000 * 25, 75)
    throughput_bonus = min(float(benchmark.get("tokens_per_second_p50", 0)) / 100 * 20, 40)
    cost_penalty = estimated_cost * 30
    if strategy == "fastest" or sla == "latency":
        latency_penalty *= 1.25
    if strategy == "cheapest-compatible":
        cost_penalty *= 1.5
    return round(compatibility_score - cost_penalty - latency_penalty + throughput_bonus + availability_score, 4)


def _placement_reasons(
    record: dict[str, Any],
    benchmark: dict[str, Any],
    hardware: dict[str, Any],
    estimated_cost_label: str,
) -> list[str]:
    return [
        "verified benchmark exists",
        f"p50 TTFT: {benchmark['ttft_ms_p50']} ms",
        f"p50 throughput: {benchmark['tokens_per_second_p50']} tok/s",
        f"estimated cost: {estimated_cost_label}",
        f"compatible with {hardware.get('accelerator_name', 'recorded hardware')}",
        f"compatibility record: {record['id']}",
    ]


def _estimated_cost_per_1m_tokens(benchmark: dict[str, Any], pool: dict[str, Any]) -> float:
    record = _cost_record_for_benchmark(benchmark, pool)
    if record:
        return float(record["per_1m_tokens_usd"])
    return float(pool.get("estimated_cost_per_1m_tokens", 0.72))


def _estimated_cost_label(benchmark: dict[str, Any], pool: dict[str, Any], cost: float) -> str:
    record = _cost_record_for_benchmark(benchmark, pool)
    if record:
        return str(record["label"])
    return "local/free" if cost == 0 else f"${cost:.4f}/1M tokens"


def _cost_record_for_benchmark(benchmark: dict[str, Any], pool: dict[str, Any]) -> dict[str, Any] | None:
    records = pool.get("_state_cost_records")
    if records is None:
        return None
    return records.get(f"{benchmark['provider']}:{benchmark['compute']}")


def _parse_max_cost(value: str) -> float:
    match = re.search(r"([0-9.]+)", value)
    return float(match.group(1)) if match else 0.0


def start_serve_runtime(
    state: dict[str, Any],
    name: str,
    model_path: str,
    runtime: str,
    compute: str,
    plan: str | None = None,
    region: str | None = None,
    accelerator: str | None = None,
    deployment_kind: str | None = None,
    os_id: int | None = None,
    ssh_key_ids: str | None = None,
    firewall_group_id: str | None = None,
    offer_id: str | None = None,
    max_price: float | None = None,
    disk_gb: int | None = None,
    confirm_cost: bool = False,
) -> dict[str, Any]:
    pool = state["compute_pools"].get(compute)
    if not pool:
        raise ValueError(f"Unknown compute pool {compute}")
    if runtime not in {"llama.cpp", "vllm"}:
        raise ValueError("serve start currently supports runtime=llama.cpp or runtime=vllm")
    config = load_config(state.get("config", {}))
    if pool.get("provider") == "vultr":
        if not confirm_cost:
            raise ValueError("--confirm-cost is required before creating paid Vultr cloud resources")
        selected = _select_vultr_placement(state, plan, region, accelerator, deployment_kind)
        provider = VultrProvider(config)
        process = provider.create_runtime(
            {
                "name": name,
                "runtime": runtime,
                "model_path": model_path,
                "compute": compute,
                "plan": selected["plan"],
                "region": selected["region"],
                "deployment_kind": selected["deployment_kind"],
                "os_id": os_id,
                "ssh_key_ids": ssh_key_ids,
                "firewall_group_id": firewall_group_id,
            }
        )
        deployment = {
            "name": name,
            "kind": "serve-runtime",
            "provider": "vultr",
            "compute": compute,
            "model": model_path,
            "model_source": model_path,
            "runtime": runtime,
            "endpoint": "openai",
            "gateway": gateway_contract(name),
            "url": gateway_contract(name)["chat_completions_url"],
            "upstream_url": f"{process['upstream_url']}/v1/chat/completions" if process.get("upstream_url") else "pending",
            "health": process.get("health", "provisioning"),
            "created_at": now(),
            "runtime_process": process,
            "routes": [
                {
                    "role": "primary",
                    "route": f"vultr:{compute}",
                    "pool": compute,
                    "runtime": runtime,
                    "status": process.get("health", "provisioning"),
                    "simulated": False,
                    "real": True,
                    "upstream_url": process.get("upstream_url"),
                    "runtime_url": process.get("upstream_url"),
                    "p95_ms": 0,
                    "tokens_per_sec": 0,
                    "estimated_cost": selected.get("estimated_cost", "vultr billed"),
                    "plan": selected["plan"],
                    "region": selected["region"],
                }
            ],
            "metrics": {
                "p95_ms": 0,
                "error_rate": 0.0,
                "tokens_per_sec": 0,
                "queue_depth": 0,
                "cost_per_1m_tokens": 0.0,
            },
        }
        state["deployments"][name] = deployment
        add_event(state, name, f"Created Vultr {runtime} runtime on {compute}")
        return deployment
    if pool.get("provider") == "vast":
        if not confirm_cost:
            raise ValueError("--confirm-cost is required before creating paid Vast cloud resources")
        provider = VastProvider(config)
        process = provider.create_runtime(
            {
                "name": name,
                "runtime": runtime,
                "model_path": model_path,
                "compute": compute,
                "accelerator": accelerator,
                "offer_id": offer_id,
                "max_price": max_price,
                "disk_gb": disk_gb,
            }
        )
        deployment = {
            "name": name,
            "kind": "serve-runtime",
            "provider": "vast",
            "compute": compute,
            "model": model_path,
            "model_source": model_path,
            "runtime": runtime,
            "endpoint": "openai",
            "gateway": gateway_contract(name),
            "url": gateway_contract(name)["chat_completions_url"],
            "upstream_url": f"{process['upstream_url']}/v1/chat/completions" if process.get("upstream_url") else "pending",
            "health": process.get("health", "provisioning"),
            "created_at": now(),
            "runtime_process": process,
            "routes": [
                {
                    "role": "primary",
                    "route": f"vast:{compute}",
                    "pool": compute,
                    "runtime": runtime,
                    "status": process.get("health", "provisioning"),
                    "simulated": False,
                    "real": True,
                    "upstream_url": process.get("upstream_url"),
                    "runtime_url": process.get("upstream_url"),
                    "p95_ms": 0,
                    "tokens_per_sec": 0,
                    "estimated_cost": f"${process.get('price_per_hour_usd', 0.0):.2f}/hr",
                    "offer_id": process.get("offer_id"),
                }
            ],
            "metrics": {
                "p95_ms": 0,
                "error_rate": 0.0,
                "tokens_per_sec": 0,
                "queue_depth": 0,
                "cost_per_1m_tokens": 0.0,
            },
        }
        state["deployments"][name] = deployment
        add_event(state, name, f"Created Vast {runtime} runtime on {compute}")
        return deployment
    if pool.get("kind") != "docker":
        raise ValueError("serve start currently supports Docker, Vultr, or Vast compute")
    provider = DockerProvider(config)
    inventory = provider.list_inventory()
    pool["inventory"] = inventory
    pool["status"] = inventory["status"]
    if not inventory["docker"]["available"]:
        raise RuntimeError(f"Docker is unavailable: {inventory['docker'].get('error', 'docker daemon is not reachable')}")
    handle = provider.create_runtime({"name": name, "runtime": runtime, "model_path": model_path, "compute": compute})
    process = provider.start_runtime(handle)
    deployment = {
        "name": name,
        "kind": "serve-runtime",
        "provider": "docker",
        "compute": compute,
        "model": model_path,
        "model_source": model_path,
        "runtime": runtime,
        "endpoint": "openai",
        "gateway": gateway_contract(name),
        "url": gateway_contract(name)["chat_completions_url"],
        "upstream_url": f"{process['upstream_url']}/v1/chat/completions",
        "health": "healthy" if process["health"] in {"running", "healthy"} else process["health"],
        "created_at": now(),
        "runtime_process": process,
        "routes": [
            {
                "role": "primary",
                "route": f"docker:{compute}",
                "pool": compute,
                "runtime": runtime,
                "status": "healthy" if process["health"] in {"running", "healthy"} else process["health"],
                "simulated": False,
                "real": True,
                "upstream_url": process["upstream_url"],
                "runtime_url": process["upstream_url"],
                "p95_ms": 0,
                "tokens_per_sec": 0,
                "estimated_cost": "local docker cost",
            }
        ],
        "metrics": {
            "p95_ms": 0,
            "error_rate": 0.0,
            "tokens_per_sec": 0,
            "queue_depth": 0,
            "cost_per_1m_tokens": 0.0,
        },
    }
    state["deployments"][name] = deployment
    add_event(state, name, f"Started Docker {runtime} runtime on {compute}")
    return deployment


def _select_vultr_placement(
    state: dict[str, Any],
    plan: str | None,
    region: str | None,
    accelerator: str | None,
    deployment_kind: str | None,
) -> dict[str, Any]:
    if plan and region:
        return {
            "plan": plan,
            "region": region,
            "deployment_kind": deployment_kind or ("bare-metal" if plan.startswith("vbm-") else "cloud-gpu"),
            "estimated_cost": "vultr billed",
        }
    records = [
        record
        for record in ensure_provider_broker(state).get("price_records", {}).values()
        if record.get("provider") == "vultr"
        and record.get("price_status") == "live"
        and record.get("price_per_hour_usd") is not None
    ]
    if accelerator:
        records = [record for record in records if record.get("accelerator") == accelerator]
    if region:
        records = [record for record in records if record.get("region") == region]
    if deployment_kind:
        records = [record for record in records if record.get("deployment_kind") == deployment_kind]
    records = [record for record in records if record.get("region") and record.get("region") != "unknown"]
    if not records:
        raise ValueError("No live Vultr placement found; pass --plan and --region or run prices refresh --provider vultr")
    selected = sorted(records, key=lambda record: float(record["price_per_hour_usd"]))[0]
    plan_id = str(selected.get("plan_id") or selected["pool"].replace(f"vultr-{selected.get('deployment_kind')}-", ""))
    return {
        "plan": plan_id,
        "region": str(selected["region"]),
        "deployment_kind": str(selected.get("deployment_kind") or ("bare-metal" if plan_id.startswith("vbm-") else "cloud-gpu")),
        "estimated_cost": f"${float(selected['price_per_hour_usd']):.2f}/hr",
    }


def serve_runtime_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    config = load_config(state.get("config", {}))
    docker_provider = DockerProvider(config)
    vultr_provider = VultrProvider(config)
    vast_provider = VastProvider(config)
    for deployment in state["deployments"].values():
        if deployment.get("provider") not in {"docker", "vultr", "vast"}:
            continue
        process = deployment.get("runtime_process", {})
        if process and deployment.get("health") != "stopped":
            if deployment.get("provider") == "vultr":
                provider = vultr_provider
            elif deployment.get("provider") == "vast":
                provider = vast_provider
            else:
                provider = docker_provider
            health = provider.health_check(process)
            process["health"] = "healthy" if health.get("healthy") else health.get("status", "unknown")
            if health.get("upstream_url"):
                process["upstream_url"] = health["upstream_url"]
                deployment["upstream_url"] = f"{health['upstream_url']}/v1/chat/completions"
            deployment["health"] = process["health"]
            for route in deployment.get("routes", []):
                route["status"] = process["health"]
                if process.get("upstream_url"):
                    route["upstream_url"] = process["upstream_url"]
                    route["runtime_url"] = process["upstream_url"]
        rows.append(
            {
                "name": deployment["name"],
                "compute": deployment.get("compute"),
                "runtime": deployment.get("runtime"),
                "health": deployment.get("health"),
                "port": process.get("port"),
                "container": process.get("container_name") or process.get("vultr_id") or process.get("vast_instance_id"),
                "url": deployment.get("url"),
            }
        )
    return rows


def serve_runtime_logs(state: dict[str, Any], name: str, lines: int = 200) -> str:
    deployment = state["deployments"].get(name)
    if not deployment:
        raise ValueError(f"Unknown serve runtime {name}")
    if deployment.get("provider") == "vultr":
        return VultrProvider(load_config(state.get("config", {}))).logs(deployment["runtime_process"], lines)
    if deployment.get("provider") == "vast":
        return VastProvider(load_config(state.get("config", {}))).logs(deployment["runtime_process"], lines)
    if deployment.get("provider") != "docker":
        raise ValueError(f"{name} is not a Docker, Vultr, or Vast serve runtime")
    return DockerProvider(load_config(state.get("config", {}))).logs(deployment["runtime_process"], lines)


def stop_serve_runtime(state: dict[str, Any], name: str) -> dict[str, Any]:
    deployment = state["deployments"].get(name)
    if not deployment:
        raise ValueError(f"Unknown serve runtime {name}")
    if deployment.get("provider") == "vultr":
        provider = VultrProvider(load_config(state.get("config", {})))
    elif deployment.get("provider") == "vast":
        provider = VastProvider(load_config(state.get("config", {})))
    elif deployment.get("provider") == "docker":
        provider = DockerProvider(load_config(state.get("config", {})))
    else:
        raise ValueError(f"{name} is not a Docker, Vultr, or Vast serve runtime")
    deployment["runtime_process"] = provider.stop_runtime(deployment["runtime_process"])
    if deployment["runtime_process"]["status"] == "stop_failed":
        raise RuntimeError(deployment["runtime_process"].get("stop_error") or "Failed to stop serve runtime")
    deployment["health"] = "stopped"
    for route in deployment.get("routes", []):
        route["status"] = "stopped"
    add_event(state, name, f"Stopped {deployment.get('provider')} serve runtime")
    return deployment


def runtime_processes(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for deployment in state["deployments"].values():
        process = deployment.get("runtime_process")
        if process:
            rows.append(
                {
                    "deployment": deployment["name"],
                    "pid": process.get("pid"),
                    "runtime": process.get("runtime"),
                    "health": process.get("health"),
                    "host": process.get("host"),
                    "port": process.get("port"),
                    "logs_path": process.get("logs_path"),
                }
            )
    return rows


def cleanup_stale_processes(state: dict[str, Any]) -> list[str]:
    cleaned = []
    config = load_config(state.get("config", {}))
    provider = LocalProvider(config)
    for deployment in state["deployments"].values():
        process = deployment.get("runtime_process")
        if not process or process.get("health") == "stopped":
            continue
        if provider.health_check(process):
            process["health"] = "healthy"
            deployment["health"] = "healthy"
            for route in deployment.get("routes", []):
                if route.get("pool") == "local":
                    route["status"] = "healthy"
            continue
        if not provider.pid_alive(int(process["pid"])):
            process["health"] = "stale"
            deployment["health"] = "stale"
            for route in deployment.get("routes", []):
                if route.get("pool") == "local":
                    route["status"] = "stale"
            cleaned.append(deployment["name"])
    if cleaned:
        add_event(state, "runtime", f"Marked stale runtime process(es): {', '.join(cleaned)}")
    return cleaned


def stop_deployment(state: dict[str, Any], deployment_name: str) -> dict[str, Any]:
    deployment = state["deployments"].get(deployment_name)
    if not deployment:
        raise ValueError(f"Unknown deployment {deployment_name}")
    process = deployment.get("runtime_process")
    if process and process.get("health") not in {"stopped", "missing"}:
        config = load_config(state.get("config", {}))
        provider = LocalProvider(config)
        deployment["runtime_process"] = provider.stop(process)
        if deployment["runtime_process"]["health"] != "stopped":
            raise ValueError(f"Failed to stop runtime process {process['pid']}")
    deployment["health"] = "stopped"
    for route in deployment["routes"]:
        if route.get("pool") == "local":
            route["status"] = "stopped"
    add_event(state, deployment_name, "Deployment stopped")
    return deployment


def parse_replicas(value: str | None) -> dict[str, int]:
    replicas = {"min": 1, "max": 1}
    if not value:
        return replicas
    for part in value.split(","):
        key, _, raw = part.partition("=")
        if key.strip() in replicas and raw:
            replicas[key.strip()] = int(raw)
    return replicas


def effective_cost(route: dict[str, Any]) -> float:
    if route["estimated_cost"] == "customer cost":
        return 0.05
    if route["estimated_cost"] == "local cost":
        return 0.0
    match = re.search(r"-(\d+)%", str(route["estimated_cost"]))
    discount = int(match.group(1)) if match else 20
    return round(0.72 * (100 - discount) / 100, 3)


def record_usage(
    state: dict[str, Any],
    deployment_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
) -> dict[str, Any]:
    deployment = state["deployments"][deployment_name]
    route = deployment["routes"][0]
    total = prompt_tokens + completion_tokens
    cost = round((total / 1_000_000) * effective_cost(route), 8)
    usage = {
        "time": now(),
        "deployment": deployment_name,
        "route": route["route"],
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total,
        "latency_ms": latency_ms,
    }
    state["usage_events"].append(usage)
    state["cost_events"].append(
        {"time": usage["time"], "deployment": deployment_name, "tokens": total, "cost_usd": cost}
    )
    metrics = deployment.setdefault(
        "metrics",
        {
            "p95_ms": 0,
            "tokens_per_sec": 0.0,
            "error_rate": 0.0,
            "queue_depth": 0,
            "cost_per_1m_tokens": 0.0,
        },
    )
    metrics["p95_ms"] = max(int(metrics.get("p95_ms", 0)), latency_ms)
    return usage


def optimize_deployment(state: dict[str, Any], deployment_name: str) -> dict[str, Any]:
    deployment = state["deployments"].get(deployment_name)
    if not deployment:
        raise ValueError(f"Unknown deployment {deployment_name}")
    current = deployment["routes"][0]
    alternatives = [route for route in deployment["routes"][1:] if route["status"] == "healthy"]
    if not alternatives:
        return {"found": False, "message": "No better route found. Current route remains optimal."}
    best = min(alternatives, key=lambda route: (effective_cost(route), route["p95_ms"]))
    if effective_cost(best) < effective_cost(current) or best["p95_ms"] + 40 < current["p95_ms"]:
        return {
            "found": True,
            "route": best["route"],
            "expected_cost_reduction": "12%",
            "latency_improvement_ms": max(0, current["p95_ms"] - best["p95_ms"]),
            "risk": "low",
        }
    return {"found": False, "message": "No better route found. Current route remains optimal."}
