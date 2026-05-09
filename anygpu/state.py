from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator


def state_dir() -> Path:
    return Path(os.environ.get("ANYGPU_HOME", ".anygpu")).expanduser()


def state_path() -> Path:
    return state_dir() / "state.json"


def initial_state() -> dict[str, Any]:
    return {
        "session": {"user": None, "current_org": None, "current_project": None},
        "config": {},
        "orgs": {},
        "projects": {},
        "compute_pools": {},
        "models": {},
        "model_records": {},
        "hardware_nodes": {},
        "runtime_profiles": {},
        "profiles": {},
        "benchmarks": {},
        "benchmark_results": [],
        "compatibility_records": [],
        "policies": {},
        "deployments": {},
        "kubernetes_manifests": {},
        "provider_broker": {
            "providers": {},
            "accelerators": {},
            "price_records": {},
            "capacity_records": {},
            "managed_pools": {},
            "refreshed_at": None,
            "source": None,
        },
        "cost_records": {},
        "events": [],
        "usage_events": [],
        "cost_events": [],
    }


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return initial_state()
    with path.open() as handle:
        loaded = json.load(handle)
    base = initial_state()
    base.update(loaded)
    return base


def save_state(state: dict[str, Any]) -> None:
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path()
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    Path(temp_name).replace(path)


@contextmanager
def edit_state() -> Iterator[dict[str, Any]]:
    state = load_state()
    yield state
    save_state(state)


def snapshot() -> dict[str, Any]:
    return deepcopy(load_state())
