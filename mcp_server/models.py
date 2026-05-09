from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class GpuOffer:
    provider: str       # "lambda", "runpod", "vast", "modal"
    instance_id: str
    gpu_type: str       # "A10G", "A100", "RTX4090", etc.
    gpu_count: int
    vram_gb: int
    price_per_hr: float
    available: bool
    region: str
    raw: Optional[dict] = None  # original provider response, for provisioning

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass
class DeployedInstance:
    provider: str
    instance_id: str
    gpu_type: str
    price_per_hr: float
    endpoint_url: str        # e.g. "http://1.2.3.4:8000/v1"
    api_key: str
    deployed_at: float       # unix timestamp
    region: str
    raw: Optional[dict] = None
