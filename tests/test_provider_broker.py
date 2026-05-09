from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from anygpu.config import load_config


ROOT = Path(__file__).resolve().parents[1]


def run_cli(home: Path, *args: str, extra_env: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    env["ANYGPU_HOME"] = str(home)
    env["PYTHONPATH"] = str(ROOT)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-m", "anygpu", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def read_state(home: Path) -> dict:
    with (home / "state.json").open() as handle:
        return json.load(handle)


def test_broker_refresh_seeds_provider_catalog_across_architectures(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"

    output = run_cli(home, "broker", "refresh")

    assert "Broker catalog refreshed" in output
    assert "providers:" in output
    state = read_state(home)
    broker = state["provider_broker"]
    assert broker["providers"]["runpod"]["architectures"] == ["nvidia"]
    assert "amd" in broker["providers"]["tensorwave"]["architectures"]
    assert "tpu" in broker["providers"]["gcp-tpu"]["architectures"]
    assert "intel-gaudi" in broker["providers"]["intel-developer-cloud"]["architectures"]
    assert "apple-silicon" in broker["providers"]["macstadium"]["architectures"]
    assert broker["price_records"]
    assert broker["capacity_records"]
    assert broker["managed_pools"]
    assert broker["managed_pools"]["managed-h100-runpod-us-secure"]["provisioning_status"] == "not_configured"


def test_broker_refresh_includes_expanded_gpu_broker_catalog(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"

    run_cli(home, "broker", "refresh")
    providers = run_cli(home, "providers", "list", "--architecture", "nvidia")
    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")
    run_cli(home, "compute", "use", "managed")
    pools = run_cli(home, "compute", "pools", "list")

    state = read_state(home)
    broker = state["provider_broker"]
    expected = {
        "nebius": ("Nebius AI Cloud", ["b200", "h200", "h100"]),
        "oci": ("Oracle Cloud Infrastructure GPU", ["b200", "h200", "h100", "l40s", "a100", "a10"]),
        "paperspace": ("DigitalOcean Paperspace", ["h100", "a100"]),
        "datacrunch": ("DataCrunch", ["b200", "h200", "h100", "a100", "l40s"]),
        "hyperstack": ("Hyperstack", ["h200", "h100", "a100"]),
        "cudo": ("Cudo Compute", ["h100", "a100", "l40s", "a40"]),
        "genesis-cloud": ("Genesis Cloud", ["b200", "h200", "h100"]),
        "voltage-park": ("Voltage Park", ["b200", "h100"]),
    }
    for provider_id, (name, accelerators) in expected.items():
        assert broker["providers"][provider_id]["name"] == name
        assert broker["providers"][provider_id]["accelerators"] == accelerators
        assert provider_id in providers
        assert name in providers

    assert "managed-b200-nebius-us" in pools
    assert "managed-h100-oci-us-ashburn-1" in pools
    assert "managed-h100-voltage-park-texas" in pools
    assert "managed-h200-genesis-cloud-fr" in broker["managed_pools"]
    assert broker["managed_pools"]["managed-b200-datacrunch-eu"]["max_vram_gb"] == 192
    assert state["cost_records"]["nebius:managed-b200-nebius-us"]["source"] == "broker_seed"


def test_providers_list_can_filter_by_architecture(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    run_cli(home, "broker", "refresh")

    output = run_cli(home, "providers", "list", "--architecture", "tpu")

    assert "gcp-tpu" in output
    assert "Google Cloud TPU" in output
    assert "runpod" not in output
    assert "credential" in output.lower()


def test_prices_and_capacity_list_seeded_broker_records(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    run_cli(home, "broker", "refresh")

    prices = run_cli(home, "prices", "list", "--accelerator", "h100")
    capacity = run_cli(home, "capacity", "list", "--architecture", "amd")

    assert "runpod" in prices
    assert "h100" in prices.lower()
    assert "seeded" in prices
    assert "unknown" in prices
    assert "tensorwave" in capacity
    assert "mi300x" in capacity.lower()
    assert "unknown" in capacity


def test_compute_use_managed_populates_pools_from_broker_catalog(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    run_cli(home, "login")
    run_cli(home, "org", "create", "acme-ai")
    run_cli(home, "project", "create", "prod-chat")

    output = run_cli(home, "compute", "use", "managed")
    pools = run_cli(home, "compute", "pools", "list")

    assert "Managed compute enabled" in output
    assert "managed-h100-runpod-us-secure" in pools
    assert "managed-mi300x-tensorwave-us-east" in pools
    assert "managed-tpu-v5e-gcp-us-central1" in pools
    assert "managed-gaudi-intel-us" in pools
    assert "managed-m4-macstadium-us" in pools
    state = read_state(home)
    pool = state["compute_pools"]["managed-tpu-v5e-gcp-us-central1"]
    assert pool["architecture"] == "tpu"
    assert pool["provider"] == "gcp-tpu"
    assert "jax-xla" in pool["runtimes"]
    assert pool["capacity_status"] == "unknown"
    assert state["cost_records"]["gcp-tpu:managed-tpu-v5e-gcp-us-central1"]["source"] == "broker_seed"


def test_prices_refresh_vast_normalizes_live_offer_records(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    payload = {
        "offers": [
            {
                "id": 101,
                "gpu_name": "NVIDIA H100 80GB HBM3",
                "gpu_arch": "nvidia",
                "num_gpus": 2,
                "gpu_ram": 81920,
                "gpu_total_ram": 163840,
                "dph_total": 4.5,
                "geolocation": "US",
                "rentable": True,
                "rented": False,
                "verification": "verified",
                "reliability": 0.998,
                "cuda_max_good": 12.4,
                "driver_version": "550.54.14",
            },
            {
                "id": 102,
                "gpu_name": "AMD Instinct MI300X OAM",
                "gpu_arch": "amd",
                "num_gpus": 1,
                "gpu_ram": 196608,
                "dph_total": 2.2,
                "geolocation": "CA",
                "rentable": True,
                "rented": False,
                "verification": "verified",
            },
        ]
    }
    response_path = tmp_path / "vast-offers.json"
    response_path.write_text(json.dumps(payload))
    env = {
        "ANYGPU_VAST_API_BASE_URL": f"file://{response_path}",
        "ANYGPU_VAST_API_KEY": "test-token",
    }

    output = run_cli(home, "prices", "refresh", "--provider", "vast", "--limit", "2", extra_env=env)

    assert "Refreshed vast prices" in output
    assert "offers: 2" in output
    state = read_state(home)
    broker = state["provider_broker"]
    h100_price = broker["price_records"]["vast:h100:US:offer-101"]
    mi300x_capacity = broker["capacity_records"]["vast:mi300x:CA:offer-102"]
    assert h100_price["price_per_hour_usd"] == 4.5
    assert h100_price["price_status"] == "live"
    assert h100_price["freshness"] == "fresh"
    assert h100_price["source"] == "vast_search_offers"
    assert h100_price["gpu_count"] == 2
    assert mi300x_capacity["available"] is True
    assert mi300x_capacity["capacity_status"] == "available"
    assert mi300x_capacity["architecture"] == "amd"

    listed = run_cli(home, "prices", "list", "--accelerator", "h100")
    assert "vast" in listed
    assert "4.5" in listed
    assert "live" in listed


def test_broker_refresh_includes_vultr_provider_and_gpu_pools(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"

    run_cli(home, "broker", "refresh")
    providers = run_cli(home, "providers", "list", "--architecture", "amd")
    pools = run_cli(home, "compute", "use", "managed")

    assert "vultr" in providers
    assert "Vultr" in providers
    assert "Managed compute enabled" in pools
    state = read_state(home)
    broker = state["provider_broker"]
    assert broker["providers"]["vultr"]["accelerators"] == ["b200", "a100", "a40", "a16", "mi355x", "mi325x"]
    assert "managed-mi355x-vultr-bare-metal" in broker["managed_pools"]
    assert "managed-a100-vultr-cloud-gpu" in broker["managed_pools"]


def test_prices_refresh_vultr_normalizes_cloud_gpu_and_bare_metal_plans(tmp_path: Path) -> None:
    home = tmp_path / "anygpu"
    payload = {
        "plans": [
            {
                "id": "vcg-a100-12c-120g-80vram",
                "vcpu_count": 12,
                "ram": 122880,
                "disk": 1400,
                "monthly_cost": 1752,
                "locations": ["ewr", "ord"],
            },
            {
                "id": "vcg-a16-6c-48g-16vram",
                "vcpu_count": 6,
                "ram": 49152,
                "disk": 200,
                "monthly_cost": 350.4,
                "locations": ["lax"],
            },
        ],
        "plans_metal": [
            {
                "id": "vbm-mi355x-8x-3tb",
                "cpu_count": 256,
                "ram": 3145728,
                "disk": 7680,
                "disk_count": 8,
                "monthly_cost": 15123.6,
                "locations": ["ord"],
            }
        ],
    }
    response_path = tmp_path / "vultr-plans.json"
    response_path.write_text(json.dumps(payload))
    env = {
        "ANYGPU_VULTR_API_BASE_URL": f"file://{response_path}",
        "VULTR_API_KEY": "test-token",
    }

    output = run_cli(home, "prices", "refresh", "--provider", "vultr", "--limit", "50", extra_env=env)

    assert "Refreshed vultr prices" in output
    assert "offers: 4" in output
    state = read_state(home)
    broker = state["provider_broker"]
    a100_price = broker["price_records"]["vultr:a100:ewr:plan-vcg-a100-12c-120g-80vram"]
    mi355x_capacity = broker["capacity_records"]["vultr:mi355x:ord:plan-vbm-mi355x-8x-3tb"]
    assert a100_price["price_per_hour_usd"] == 2.4
    assert a100_price["gpu_count"] == 1
    assert a100_price["deployment_kind"] == "cloud-gpu"
    assert a100_price["source"] == "vultr_plans_api"
    assert mi355x_capacity["architecture"] == "amd"
    assert mi355x_capacity["available"] is True
    assert mi355x_capacity["deployment_kind"] == "bare-metal"

    listed = run_cli(home, "prices", "list", "--accelerator", "mi355x")
    assert "vultr" in listed
    assert "20.72" in listed
    assert "live" in listed


def test_config_accepts_vultr_api_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("ANYGPU_VULTR_API_KEY", raising=False)
    monkeypatch.setenv("VULTR_API_KEY", "vultr-token")

    config = load_config({})

    assert config["vultr_api_key"] == "vultr-token"


def test_config_accepts_vast_ai_api_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("ANYGPU_VAST_API_KEY", raising=False)
    monkeypatch.setenv("VAST_AI_API_KEY", "test-token")

    config = load_config({})

    assert config["vast_api_key"] == "test-token"


def test_config_loads_repo_dotenv_without_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANYGPU_VAST_API_KEY", raising=False)
    monkeypatch.delenv("VAST_AI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("VAST_AI_API_KEY=dotenv-token\n")

    config = load_config({})

    assert config["vast_api_key"] == "dotenv-token"


def test_prices_refresh_vast_requires_api_key_for_https() -> None:
    home = Path("/tmp/anygpu-unused")
    env = {
        "ANYGPU_VAST_API_BASE_URL": "https://console.vast.ai/api/v0/bundles/",
        "ANYGPU_VAST_API_KEY": "",
        "VAST_AI_API_KEY": "",
    }
    result = subprocess.run(
        [sys.executable, "-m", "anygpu", "prices", "refresh", "--provider", "vast"],
        cwd=ROOT,
        env={**os.environ, "ANYGPU_HOME": str(home), "PYTHONPATH": str(ROOT), **env},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "vast_api_key is required" in result.stderr
