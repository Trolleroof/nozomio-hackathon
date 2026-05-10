import asyncio
from dataclasses import dataclass

from experiments.provider_price_check import collect_provider_offers


@dataclass
class FakeOffer:
    provider: str
    gpu_type: str
    gpu_count: int
    vram_gb: int
    price_per_hr: float
    available: bool
    region: str


async def ok_fetch():
    return [
        FakeOffer("runpod", "RTX 4090", 1, 24, 0.42, True, "global"),
        FakeOffer("runpod", "A100", 1, 40, 2.0, False, "global"),
    ]


async def failing_fetch():
    raise RuntimeError("secret-token should not leak")


def test_collect_provider_offers_sorts_available_offers_and_sanitizes_errors() -> None:
    result = asyncio.run(collect_provider_offers({"ok": ok_fetch, "bad": failing_fetch}))

    assert result["offer_count"] == 1
    assert result["top_offers"] == [
        {
            "provider": "runpod",
            "gpu_type": "RTX 4090",
            "gpu_count": 1,
            "vram_gb": 24,
            "price_per_hr": 0.42,
            "available": True,
            "region": "global",
        }
    ]
    assert result["recommended_offer"] == result["top_offers"][0]
    assert result["estimated_cost_for_10_min"] == 0.07
    assert result["errors"] == [
        {
            "provider": "bad",
            "error_type": "RuntimeError",
            "error": "[redacted]",
        }
    ]
