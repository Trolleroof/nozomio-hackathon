import json
import asyncio

from mcp_server.providers import vast_ai


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
