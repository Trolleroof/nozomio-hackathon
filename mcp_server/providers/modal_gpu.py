import os
from typing import List
from ..models import GpuOffer

# Modal GPU pricing (USD/hr, as of 2025) — updated manually when rates change
_MODAL_GPU_PRICES: dict[str, tuple[int, float]] = {
    # gpu_type: (vram_gb, price_per_hr)
    "A10G":   (24, 1.10),
    "A100":   (40, 3.09),
    "A100-80GB": (80, 3.95),
    "H100":   (80, 6.00),
    "T4":     (16, 0.59),
}


async def fetch() -> List[GpuOffer]:
    """Returns static Modal GPU pricing as GpuOffer objects.

    Modal doesn't expose a price-list API; rates are published on their docs page
    and encoded here. Modal bills per-second so $/hr is the ceiling rate.
    """
    offers: List[GpuOffer] = []
    for gpu_type, (vram_gb, price_per_hr) in _MODAL_GPU_PRICES.items():
        offers.append(GpuOffer(
            provider="modal",
            instance_id=f"modal:{gpu_type}",
            gpu_type=gpu_type,
            gpu_count=1,
            vram_gb=vram_gb,
            price_per_hr=price_per_hr,
            available=True,
            region="us-east",
            raw={"gpu_type": gpu_type, "price_per_hr": price_per_hr},
        ))
    return offers


def build_modal_app(gpu_type: str, vllm_api_key: str) -> str:
    """Returns a self-contained modal_deploy.py script to be run via `modal run`."""
    return f"""
import modal

app = modal.App("qwen-vllm")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("vllm>=0.4.0")
)

@app.function(
    image=image,
    gpu="{gpu_type}",
    timeout=3600,
    secrets=[modal.Secret.from_dict({{"VLLM_API_KEY": "{vllm_api_key}"}})],
)
@modal.web_server(8000)
def serve():
    import subprocess, os
    subprocess.Popen([
        "vllm", "serve", "Qwen/Qwen2.5-7B-Instruct",
        "--served-model-name", "qwen",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--api-key", os.environ["VLLM_API_KEY"],
    ])
"""
