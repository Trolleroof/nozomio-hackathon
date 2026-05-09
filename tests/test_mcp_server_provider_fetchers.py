import json
import asyncio

import pytest

from mcp_server.providers import runpod, vast_ai


def test_runpod_fetch_rejects_blank_api_key(monkeypatch) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "")

    with pytest.raises(RuntimeError, match="RUNPOD_API_KEY is required"):
        asyncio.run(runpod.fetch())


def test_vast_fetch_rejects_blank_api_key(monkeypatch) -> None:
    monkeypatch.setenv("VAST_API_KEY", "")

    with pytest.raises(RuntimeError, match="VAST_API_KEY is required"):
        asyncio.run(vast_ai.fetch())


def test_vast_fetch_follows_provider_redirects(monkeypatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"offers": []}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return FakeResponse()

    monkeypatch.setenv("VAST_API_KEY", "test-token")
    monkeypatch.setattr(vast_ai.httpx, "AsyncClient", FakeAsyncClient)

    asyncio.run(vast_ai.fetch())

    assert captured["kwargs"]["follow_redirects"] is True


def test_vast_fetch_sends_json_query(monkeypatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"offers": []}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *args, **kwargs):
            captured["kwargs"] = kwargs
            return FakeResponse()

    monkeypatch.setenv("VAST_API_KEY", "test-token")
    monkeypatch.setattr(vast_ai.httpx, "AsyncClient", FakeAsyncClient)

    asyncio.run(vast_ai.fetch())

    query = json.loads(captured["kwargs"]["params"]["q"])
    assert query["gpu_ram"] == {"gte": 16384}
    assert query["rentable"] == {"eq": True}
