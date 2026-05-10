from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mcp_server.models import GpuOffer
from mcp_server import deploy as deploy_module
from mcp_server.providers import lambda_labs
from anygpu.crucible import list_provider_capabilities
from anygpu.crucible_store import CrucibleStore


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise lambda_labs.httpx.HTTPStatusError("failed", request=None, response=None)

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeAsyncClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self.responses.pop(0)

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.responses.pop(0)


def lambda_catalog_payload() -> dict[str, Any]:
    return {
        "data": {
            "gpu_1x_a10": {
                "instance_type": {
                    "name": "gpu_1x_a10",
                    "description": "1x A10 (24 GB PCIe)",
                    "gpu_description": "A10 (24 GB PCIe)",
                    "price_cents_per_hour": 129,
                    "specs": {"gpus": 1, "vcpus": 30, "memory_gib": 200, "storage_gib": 1400},
                },
                "regions_with_capacity_available": [{"name": "us-east-1", "description": "Virginia, USA"}],
            },
            "gpu_8x_v100_n": {
                "instance_type": {
                    "name": "gpu_8x_v100_n",
                    "description": "8x Tesla V100 (16 GB)",
                    "gpu_description": "Tesla V100 (16 GB)",
                    "price_cents_per_hour": 632,
                    "specs": {"gpus": 8, "vcpus": 88, "memory_gib": 448, "storage_gib": 5900},
                },
                "regions_with_capacity_available": [],
            },
        }
    }


def test_fetch_uses_lambda_cloud_api_key_and_parses_gpu_description(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LAMBDA_API_KEY", raising=False)
    monkeypatch.setenv("LAMBDA_CLOUD_API_KEY", "cloud-key")
    client = FakeAsyncClient([FakeResponse(lambda_catalog_payload())])
    monkeypatch.setattr(lambda_labs.httpx, "AsyncClient", lambda: client)

    offers = asyncio.run(lambda_labs.fetch())

    assert len(offers) == 2
    assert client.calls[0]["auth"] == ("cloud-key", "")
    assert offers[0].instance_id == "gpu_1x_a10"
    assert offers[0].gpu_type == "1x A10 (24 GB PCIe)"
    assert offers[0].gpu_count == 1
    assert offers[0].vram_gb == 24
    assert offers[0].price_per_hr == 1.29
    assert offers[0].available is True
    assert offers[0].region == "us-east-1"
    assert offers[0].raw["lambda_credential_env"] == "LAMBDA_CLOUD_API_KEY"
    assert offers[1].vram_gb == 16
    assert offers[1].available is False


def test_fetch_falls_back_between_lambda_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAMBDA_CLOUD_API_KEY", "bad-key")
    monkeypatch.setenv("LAMBDA_API_KEY", "good-key")
    client = FakeAsyncClient([FakeResponse({}, status_code=401), FakeResponse(lambda_catalog_payload())])
    monkeypatch.setattr(lambda_labs.httpx, "AsyncClient", lambda: client)

    offers = asyncio.run(lambda_labs.fetch())

    assert len(offers) == 2
    assert [call["auth"][0] for call in client.calls] == ["bad-key", "good-key"]
    assert {offer.raw["lambda_credential_env"] for offer in offers} == {"LAMBDA_API_KEY"}


def test_launch_uses_offer_credential_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAMBDA_CLOUD_API_KEY", "cloud-key")
    monkeypatch.setenv("LAMBDA_API_KEY", "api-key")
    client = FakeAsyncClient([FakeResponse({"data": {"instance_ids": ["i-123"]}})])
    monkeypatch.setattr(lambda_labs.httpx, "AsyncClient", lambda: client)
    offer = GpuOffer(
        provider="lambda",
        instance_id="gpu_1x_a10",
        gpu_type="1x A10 (24 GB PCIe)",
        gpu_count=1,
        vram_gb=24,
        price_per_hr=1.29,
        available=True,
        region="us-east-1",
        raw={"lambda_credential_env": "LAMBDA_API_KEY"},
    )

    result = asyncio.run(lambda_labs.launch(offer, ssh_key_name="agent-key"))

    assert result["data"]["instance_ids"] == ["i-123"]
    assert client.calls[0]["auth"] == ("api-key", "")
    assert client.calls[0]["json"]["ssh_key_names"] == ["agent-key"]


def test_ssh_bootstrap_uses_available_ed25519_key(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "id_ed25519").write_text("private-key")
    monkeypatch.setenv("HOME", str(tmp_path))

    assert deploy_module._default_ssh_client_keys() == [str(ssh_dir / "id_ed25519")]


def test_crucible_registry_advertises_both_lambda_key_names(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("LAMBDA_CLOUD_API_KEY", "cloud-key")
    monkeypatch.delenv("LAMBDA_API_KEY", raising=False)

    capabilities = list_provider_capabilities(CrucibleStore())

    lambda_cloud = {item["provider"]: item for item in capabilities}["Lambda Cloud"]
    assert lambda_cloud["status"] == "configured"
    assert lambda_cloud["supports_deploy"] is True
    assert lambda_cloud["credentials_required"] == ["LAMBDA_CLOUD_API_KEY", "LAMBDA_API_KEY", "LAMBDA_SSH_KEY_NAME"]
    assert "launch adapter" in lambda_cloud["notes"]
