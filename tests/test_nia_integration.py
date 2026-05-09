import json
from pathlib import Path

from anygpu.crucible import search_context
from anygpu.nia import NiaClient, is_configured, search_nia_context


def test_nia_configuration_loads_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NIA_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("NIA_API_KEY=test-nia-token\n")

    assert is_configured() is True


def test_nia_search_normalizes_live_sources(monkeypatch) -> None:
    calls = []

    def request_json(url: str, headers: dict[str, str], payload: dict, timeout: float) -> dict:
        calls.append({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
        return {
            "answer": "Use a single economical GPU for Qwen 7B and verify /v1/models.",
            "sources": [
                {
                    "title": "Qwen deployment recipe",
                    "source": "nia://repo/recipes/qwen",
                    "text": "Prefer one L4-class GPU first. Verify OpenAI-compatible health endpoints before routing traffic.",
                }
            ],
        }

    client = NiaClient(api_key="test-nia-token", request_json=request_json)

    snippets = client.search("Qwen 7B health check")

    assert calls[0]["url"].endswith("/search")
    assert calls[0]["headers"]["Authorization"] == "Bearer test-nia-token"
    assert calls[0]["payload"]["mode"] == "query"
    assert calls[0]["payload"]["messages"] == [{"role": "user", "content": "Qwen 7B health check"}]
    assert snippets == [
        {
            "title": "Qwen deployment recipe",
            "source": "nia://repo/recipes/qwen",
            "snippet": "Prefer one L4-class GPU first. Verify OpenAI-compatible health endpoints before routing traffic.",
        }
    ]


def test_nia_search_falls_back_without_leaking_secret(monkeypatch) -> None:
    monkeypatch.setenv("NIA_API_KEY", "test-nia-token")

    def failing_request(*_args, **_kwargs) -> dict:
        raise RuntimeError("upstream included test-nia-token in its error")

    snippets = search_nia_context("health check", request_json=failing_request)

    assert snippets
    encoded = json.dumps(snippets)
    assert "test-nia-token" not in encoded
    assert "Nia search unavailable" in encoded


def test_crucible_search_context_prefers_nia_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("NIA_API_KEY", "test-nia-token")

    def request_json(*_args, **_kwargs) -> dict:
        return {
            "sources": [
                {
                    "title": "Live Nia provider notes",
                    "url": "nia://workspace/provider-notes",
                    "content": "Vast.ai is connected and should be checked before launching paid compute.",
                }
            ]
        }

    snippets = search_context(None, "Vast connected", request_json=request_json)

    assert snippets[0]["title"] == "Live Nia provider notes"
    assert snippets[0]["source"] == "nia://workspace/provider-notes"
    assert "Vast.ai is connected" in snippets[0]["snippet"]
