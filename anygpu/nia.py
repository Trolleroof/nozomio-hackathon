from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .config import load_config


NIA_DEFAULT_BASE_URL = "https://apigcp.trynia.ai/v2"
NIA_FALLBACK_SNIPPETS = [
    {
        "title": "Nia search unavailable",
        "source": "crucible-cache",
        "snippet": "Live Nia context could not be reached, so Crucible is using cached deployment guidance.",
    },
    {
        "title": "Approval gate",
        "source": "Crucible policy",
        "snippet": "Paid GPU launches require explicit approval before provider resources are created.",
    },
    {
        "title": "Known working recipes",
        "source": "known working recipes",
        "snippet": "For Qwen 7B, prefer a single economical GPU first and avoid multi-GPU unless latency requires it.",
    },
]

RequestJson = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


class NiaClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        request_json: RequestJson | None = None,
        timeout: float = 15,
    ) -> None:
        config = load_config()
        self.api_key = api_key if api_key is not None else config.get("nia_api_key")
        self.base_url = (base_url or config.get("nia_api_base_url") or NIA_DEFAULT_BASE_URL).rstrip("/")
        self.request_json = request_json or _post_json
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        if not self.configured:
            raise RuntimeError("NIA_API_KEY is required for live Nia search.")
        payload = {
            "mode": "query",
            "messages": [{"role": "user", "content": query}],
            "search_mode": "unified",
            "include_sources": True,
            "fast_mode": True,
            "max_tokens": 1200,
        }
        response = self.request_json(
            f"{self.base_url}/search",
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload,
            self.timeout,
        )
        return normalize_search_response(response, limit=limit)


def is_configured() -> bool:
    return bool(load_config().get("nia_api_key"))


def search_nia_context(
    query: str,
    *,
    request_json: RequestJson | None = None,
    limit: int = 5,
) -> list[dict[str, str]]:
    client = NiaClient(request_json=request_json)
    if not client.configured:
        return list(NIA_FALLBACK_SNIPPETS)
    try:
        snippets = client.search(query, limit=limit)
    except Exception:
        return list(NIA_FALLBACK_SNIPPETS)
    return snippets or list(NIA_FALLBACK_SNIPPETS)


def normalize_search_response(response: dict[str, Any], *, limit: int = 5) -> list[dict[str, str]]:
    candidates = _candidate_items(response)
    snippets: list[dict[str, str]] = []
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue
        title = (
            _first_text(item, "title", "name", "display_name", "file", "path")
            or _nested_text(item, "source", "display_name", "file_path", "document_name", "url")
            or f"Nia result {index + 1}"
        )
        source = _first_text(item, "source", "url", "uri", "repository", "file_path", "path", "source_id") or "nia://search"
        snippet = _first_text(item, "snippet", "excerpt", "text", "content", "body", "answer", "summary")
        if not snippet:
            continue
        snippets.append(
            {
                "title": _clean(title, 120),
                "source": _clean(source, 160),
                "snippet": _clean(snippet, 360),
            }
        )
        if len(snippets) >= limit:
            return snippets

    if snippets:
        return snippets

    answer = _first_text(response, "answer", "content", "text", "summary")
    if answer:
        return [
            {
                "title": "Nia answer",
                "source": "nia://search",
                "snippet": _clean(answer, 360),
            }
        ]
    return []


def _candidate_items(response: dict[str, Any]) -> list[Any]:
    for key in ("sources", "results", "documents", "matches", "items", "data"):
        value = response.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _candidate_items(value)
            if nested:
                return nested
    return []


def _first_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            nested = _first_text(
                value,
                "title",
                "name",
                "display_name",
                "file_path",
                "url",
                "path",
                "text",
                "content",
                "snippet",
            )
            if nested:
                return nested
    return None


def _nested_text(item: dict[str, Any], key: str, *nested_keys: str) -> str | None:
    value = item.get(key)
    if not isinstance(value, dict):
        return None
    return _first_text(value, *nested_keys)


def _clean(value: str, max_length: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = getattr(exc, "status", exc.code)
        raise RuntimeError(f"Nia search failed with HTTP {status}") from exc
