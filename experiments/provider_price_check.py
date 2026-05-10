from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.providers import fetch_lambda, fetch_modal, fetch_runpod, fetch_vast


DEFAULT_OUTPUT = Path(".anygpu/rl_runs/provider_price_check.json")
SECRET_WORDS = ("key", "token", "secret", "bearer")
DEFAULT_ESTIMATE_MINUTES = 10


Fetcher = Callable[[], Awaitable[list[Any]]]


def _safe_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if any(word in lowered for word in SECRET_WORDS):
        return "[redacted]"
    return message[:300]


async def collect_provider_offers(fetchers: dict[str, Fetcher] | None = None, *, top_n: int = 15) -> dict[str, Any]:
    selected = fetchers or {
        "lambda": fetch_lambda,
        "runpod": fetch_runpod,
        "vast": fetch_vast,
        "modal": fetch_modal,
    }
    offers: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for name, fetch in selected.items():
        try:
            fetched = await fetch()
        except Exception as exc:
            errors.append({"provider": name, "error_type": type(exc).__name__, "error": _safe_error(exc)})
            continue
        for offer in fetched:
            if not getattr(offer, "available", False):
                continue
            offers.append(
                {
                    "provider": offer.provider,
                    "gpu_type": offer.gpu_type,
                    "gpu_count": offer.gpu_count,
                    "vram_gb": offer.vram_gb,
                    "price_per_hr": offer.price_per_hr,
                    "available": offer.available,
                    "region": offer.region,
                }
            )

    offers.sort(key=lambda item: item["price_per_hr"])
    recommended = offers[0] if offers else None
    estimated_cost = None
    if recommended is not None:
        estimated_cost = round(recommended["price_per_hr"] * DEFAULT_ESTIMATE_MINUTES / 60.0, 6)
    return {
        "top_offers": offers[:top_n],
        "offer_count": len(offers),
        "recommended_offer": recommended,
        "estimated_cost_for_10_min": estimated_cost,
        "errors": errors,
        "safe_to_launch": False,
        "notes": "Read-only price/availability check. No resources were launched.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a read-only GPU provider price/availability check.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-n", type=int, default=15)
    args = parser.parse_args()

    result = asyncio.run(collect_provider_offers(top_n=args.top_n))
    output = json.dumps(result, indent=2, sort_keys=True)
    print(output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output)
    print(f"artifact_path={args.output}")


if __name__ == "__main__":
    main()
