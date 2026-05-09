from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mcp_server.models import GpuOffer
from mcp_server.providers import runpod


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeAsyncClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.posts: list[dict[str, Any]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        return FakeResponse(self.payload)


def test_launch_omits_bid_price_for_on_demand_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-token")
    client = FakeAsyncClient({"data": {"podFindAndDeployOnDemand": {"id": "pod_123", "imageName": "runpod/pytorch"}}})
    monkeypatch.setattr(runpod.httpx, "AsyncClient", lambda: client)
    offer = GpuOffer(
        provider="runpod",
        instance_id="spot:NVIDIA RTX A4000",
        gpu_type="RTX A4000",
        gpu_count=1,
        vram_gb=16,
        price_per_hr=0.14,
        available=True,
        region="global",
    )

    pod = asyncio.run(runpod.launch(offer))

    launch_input = client.posts[0]["json"]["variables"]["input"]
    assert pod["id"] == "pod_123"
    assert launch_input["gpuTypeId"] == "NVIDIA RTX A4000"
    assert launch_input["cloudType"] == "ALL"
    assert launch_input["imageName"] == "runpod/pytorch"
    assert launch_input["volumeMountPath"] == "/workspace"
    assert launch_input["name"].startswith("anygpu-")
    assert "bidPerGpu" not in launch_input


def test_fetch_uses_on_demand_price_for_launchable_offers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-token")
    client = FakeAsyncClient(
        {
            "data": {
                "gpuTypes": [
                    {
                        "id": "NVIDIA RTX A4000",
                        "displayName": "RTX A4000",
                        "memoryInGb": 16,
                        "lowestPrice": {"minimumBidPrice": 0.14, "uninterruptablePrice": 0.17},
                    }
                ]
            }
        }
    )
    monkeypatch.setattr(runpod.httpx, "AsyncClient", lambda: client)

    offers = asyncio.run(runpod.fetch())

    assert len(offers) == 1
    assert offers[0].instance_id == "ondemand:NVIDIA RTX A4000"
    assert offers[0].price_per_hr == 0.17


def test_launch_raises_graphql_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-token")
    client = FakeAsyncClient({"errors": [{"message": "Field bidPerGpu is not defined"}]})
    monkeypatch.setattr(runpod.httpx, "AsyncClient", lambda: client)
    offer = GpuOffer(
        provider="runpod",
        instance_id="spot:NVIDIA RTX A4000",
        gpu_type="RTX A4000",
        gpu_count=1,
        vram_gb=16,
        price_per_hr=0.14,
        available=True,
        region="global",
    )

    with pytest.raises(RuntimeError, match="Field bidPerGpu is not defined"):
        asyncio.run(runpod.launch(offer))
