from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mcp_server.models import GpuOffer
from mcp_server import deploy as deploy_module
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


class SequenceAsyncClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads
        self.posts: list[dict[str, Any]] = []

    async def __aenter__(self) -> "SequenceAsyncClient":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        payload = self.payloads.pop(0)
        return FakeResponse(payload)


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


def test_deploy_runpod_launch_mutation_matches_current_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-token")
    client = FakeAsyncClient(
        {
            "data": {
                "podFindAndDeployOnDemand": {
                    "id": "pod_123",
                    "machine": {"podHostId": "host_123"},
                    "runtime": {"ports": []},
                }
            }
        }
    )
    monkeypatch.setattr("httpx.AsyncClient", lambda: client)
    monkeypatch.setattr(deploy_module, "_poll_runpod_endpoint", _fake_poll_runpod_endpoint)
    offer = GpuOffer(
        provider="runpod",
        instance_id="ondemand:NVIDIA RTX A5000",
        gpu_type="RTX A5000",
        gpu_count=1,
        vram_gb=24,
        price_per_hr=0.16,
        available=True,
        region="global",
    )

    instance = asyncio.run(deploy_module._deploy_runpod(offer, "test-vllm-key"))

    launch_query = client.posts[0]["json"]["query"]
    assert instance.instance_id == "pod_123"
    assert "publicIp" not in launch_query
    assert "podHostId" in launch_query


def test_deploy_runpod_surfaces_graphql_launch_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-token")
    client = FakeAsyncClient(
        {
            "errors": [
                {
                    "message": "Something went wrong. Please try again later or contact support.",
                    "path": ["podFindAndDeployOnDemand"],
                }
            ],
            "data": {"podFindAndDeployOnDemand": None},
        }
    )
    monkeypatch.setattr("httpx.AsyncClient", lambda: client)
    offer = GpuOffer(
        provider="runpod",
        instance_id="ondemand:NVIDIA RTX A5000",
        gpu_type="RTX A5000",
        gpu_count=1,
        vram_gb=24,
        price_per_hr=0.16,
        available=True,
        region="global",
    )

    with pytest.raises(RuntimeError, match="Something went wrong"):
        asyncio.run(deploy_module._deploy_runpod(offer, "test-vllm-key"))


def test_poll_runpod_endpoint_tolerates_transient_null_pod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "test-token")
    client = SequenceAsyncClient([
        {"data": {"pod": None}},
        {
            "data": {
                "pod": {
                    "id": "pod_123",
                    "runtime": {
                        "ports": [
                            {
                                "privatePort": 8000,
                                "isIpPublic": False,
                            }
                        ]
                    },
                }
            }
        },
    ])
    monkeypatch.setattr("httpx.AsyncClient", lambda: client)
    monkeypatch.setattr(deploy_module, "_wait_for_endpoint", _endpoint_ready)

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    endpoint = asyncio.run(deploy_module._poll_runpod_endpoint("pod_123", "test-vllm-key", timeout=30))

    assert endpoint == "https://pod_123-8000.proxy.runpod.net/v1"
    assert len(client.posts) == 2


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


async def _fake_poll_runpod_endpoint(_pod_id: str, _vllm_api_key: str, timeout: int = 600) -> str:
    return "http://127.0.0.1:8000/v1"


async def _endpoint_ready(_url: str, api_key: str | None = None, timeout: int = 600) -> bool:
    return True


def test_modal_credentials_can_load_from_local_modal_config(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_SECRET", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".modal.toml").write_text(
        '[test-profile]\n'
        'token_id = "local-token-id"\n'
        'token_secret = "local-token-secret"\n'
    )

    assert deploy_module._required_env("MODAL_TOKEN_ID") == "local-token-id"
    assert deploy_module._required_env("MODAL_TOKEN_SECRET") == "local-token-secret"
