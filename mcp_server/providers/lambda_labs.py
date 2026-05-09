import os
import re
import httpx
from typing import Any, List
from ..models import GpuOffer

BASE_URL = "https://cloud.lambdalabs.com/api/v1"
MIN_VRAM_GB = 16
API_KEY_ENV_NAMES = ("LAMBDA_CLOUD_API_KEY", "LAMBDA_API_KEY")


async def fetch() -> List[GpuOffer]:
    offers_by_key: dict[tuple[str, str], GpuOffer] = {}
    errors: list[str] = []
    for credential_env, api_key in _candidate_api_keys():
        try:
            data = await _get_json("/instance-types", api_key)
        except httpx.HTTPStatusError as exc:
            errors.append(f"{credential_env}: {_http_error_message(exc)}")
            continue
        except Exception as exc:
            errors.append(f"{credential_env}: {exc}")
            continue

        for offer in _parse_offers(data, credential_env):
            dedupe_key = (offer.instance_id, offer.region)
            existing = offers_by_key.get(dedupe_key)
            if existing is None or (offer.available and not existing.available):
                offers_by_key[dedupe_key] = offer

    if offers_by_key:
        return sorted(offers_by_key.values(), key=lambda offer: offer.price_per_hr)
    if errors:
        raise RuntimeError(f"Lambda Cloud API failed for configured credentials: {'; '.join(errors)}")
    return []


async def _get_json(path: str, api_key: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}{path}",
            auth=(api_key, ""),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


def _parse_offers(data: dict[str, Any], credential_env: str) -> List[GpuOffer]:
    offers: List[GpuOffer] = []
    for name, info in data.get("data", {}).items():
        specs = info.get("instance_type", {})
        gpu_specs = specs.get("specs", {})
        vram_gb = _gpu_memory_gb(specs)
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
            raw={**info, "lambda_credential_env": credential_env},
        ))

    return offers


async def launch(offer: GpuOffer, ssh_key_name: str) -> dict:
    return await _post_json(
        "/instance-operations/launch",
        {
            "region_name": offer.region,
            "instance_type_name": offer.instance_id,
            "ssh_key_names": [ssh_key_name],
            "quantity": 1,
        },
        preferred_env=_offer_credential_env(offer),
    )


async def terminate(instance_id: str) -> dict:
    return await _post_json("/instance-operations/terminate", {"instance_ids": [instance_id]})


async def get_instance(instance_id: str) -> dict:
    return (await _get_json_with_candidates(f"/instances/{instance_id}")).get("data", {})


async def _post_json(path: str, payload: dict[str, Any], *, preferred_env: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    for credential_env, api_key in _candidate_api_keys(preferred_env):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{BASE_URL}{path}",
                    auth=(api_key, ""),
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            errors.append(f"{credential_env}: {_http_error_message(exc)}")
    raise RuntimeError(f"Lambda Cloud API failed for configured credentials: {'; '.join(errors)}")


async def _get_json_with_candidates(path: str, *, preferred_env: str | None = None) -> dict[str, Any]:
    errors: list[str] = []
    for credential_env, api_key in _candidate_api_keys(preferred_env):
        try:
            return await _get_json(path, api_key)
        except httpx.HTTPStatusError as exc:
            errors.append(f"{credential_env}: {_http_error_message(exc)}")
    raise RuntimeError(f"Lambda Cloud API failed for configured credentials: {'; '.join(errors)}")


def _candidate_api_keys(preferred_env: str | None = None) -> list[tuple[str, str]]:
    env_names = list(API_KEY_ENV_NAMES)
    if preferred_env in env_names:
        env_names.remove(preferred_env)
        env_names.insert(0, preferred_env)

    candidates: list[tuple[str, str]] = []
    seen_values: set[str] = set()
    for env_name in env_names:
        value = os.environ.get(env_name)
        if value and value not in seen_values:
            candidates.append((env_name, value))
            seen_values.add(value)
    if not candidates:
        raise RuntimeError("LAMBDA_CLOUD_API_KEY or LAMBDA_API_KEY is required.")
    return candidates


def _offer_credential_env(offer: GpuOffer) -> str | None:
    raw = offer.raw or {}
    credential_env = raw.get("lambda_credential_env")
    return credential_env if isinstance(credential_env, str) else None


def _gpu_memory_gb(instance_type: dict[str, Any]) -> int:
    specs = instance_type.get("specs") or {}
    direct = specs.get("gpu_memory_gib") or specs.get("gpu_memory_gb")
    if direct:
        return int(direct)

    text = f"{instance_type.get('gpu_description', '')} {instance_type.get('description', '')}"
    match = re.search(r"\((\d+(?:\.\d+)?)\s*GB", text)
    if match:
        return int(float(match.group(1)))
    return 0


def _http_error_message(exc: httpx.HTTPStatusError) -> str:
    response = exc.response
    if response is None:
        return str(exc)
    return f"{response.status_code} {response.text[:300]}"
