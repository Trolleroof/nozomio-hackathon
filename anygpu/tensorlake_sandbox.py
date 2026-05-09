from __future__ import annotations

import importlib
import os
from collections.abc import Iterable
from typing import Any


DEFAULT_IMAGE = "tensorlake/ubuntu-minimal"
DEFAULT_CPUS = 1.0
DEFAULT_MEMORY_MB = 1024
DEFAULT_DISK_MB = 10240
DEFAULT_TIMEOUT_SECS = 300


def create_sandbox(
    *,
    image: str = DEFAULT_IMAGE,
    cpus: float = DEFAULT_CPUS,
    memory_mb: int = DEFAULT_MEMORY_MB,
    disk_mb: int = DEFAULT_DISK_MB,
    timeout_secs: int = DEFAULT_TIMEOUT_SECS,
    name: str | None = None,
) -> dict[str, Any]:
    """Create a Tensorlake sandbox for agent tool execution."""
    sandbox_cls = _sandbox_class()
    sandbox = sandbox_cls.create(
        image=image,
        cpus=cpus,
        memory_mb=memory_mb,
        disk_mb=disk_mb,
        timeout_secs=timeout_secs,
        name=name,
    )
    return {
        "sandbox_id": sandbox.sandbox_id,
        "name": getattr(sandbox, "name", name),
        "status": _json_value(getattr(sandbox, "status", None)),
        "image": getattr(sandbox, "image", image),
        "resources": {
            "cpus": cpus,
            "memory_mb": memory_mb,
            "disk_mb": disk_mb,
            "timeout_secs": timeout_secs,
        },
    }


def run_command(
    *,
    command: str,
    sandbox_id: str | None = None,
    name: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    working_dir: str | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run a command inside an existing Tensorlake sandbox."""
    sandbox = _connect(sandbox_id=sandbox_id, name=name)
    kwargs: dict[str, Any] = {}
    if args is not None:
        kwargs["args"] = args
    if env is not None:
        kwargs["env"] = env
    if working_dir is not None:
        kwargs["working_dir"] = working_dir
    if timeout is not None:
        kwargs["timeout"] = timeout
    result = sandbox.run(command, **kwargs)
    return {
        "stdout": getattr(result, "stdout", ""),
        "stderr": getattr(result, "stderr", ""),
        "exit_code": getattr(result, "exit_code", getattr(result, "returncode", None)),
    }


def terminate_sandbox(*, sandbox_id: str | None = None, name: str | None = None) -> dict[str, Any]:
    """Terminate an existing Tensorlake sandbox by ID or name."""
    sandbox = _connect(sandbox_id=sandbox_id, name=name)
    resolved_id = getattr(sandbox, "sandbox_id", sandbox_id or name)
    sandbox.terminate()
    return {"sandbox_id": resolved_id, "status": "terminated"}


def list_sandboxes() -> list[dict[str, Any]]:
    """List Tensorlake sandboxes visible to the configured API key."""
    sandbox_cls = _sandbox_class()
    return [_sandbox_info_to_dict(item) for item in sandbox_cls.list()]


def is_configured() -> bool:
    return bool(os.environ.get("TENSORLAKE_API_KEY"))


def _connect(*, sandbox_id: str | None = None, name: str | None = None) -> Any:
    ref = sandbox_id or name
    if not ref:
        raise ValueError("sandbox_id or name is required.")
    return _sandbox_class().connect(ref)


def _sandbox_class() -> Any:
    _require_api_key()
    try:
        module = importlib.import_module("tensorlake.sandbox")
    except ModuleNotFoundError as exc:
        raise RuntimeError("Tensorlake SDK is not installed. Install the `tensorlake` package to use sandbox tools.") from exc
    return module.Sandbox


def _require_api_key() -> None:
    if not os.environ.get("TENSORLAKE_API_KEY"):
        raise RuntimeError("TENSORLAKE_API_KEY is required to use Tensorlake sandbox tools.")


def _sandbox_info_to_dict(item: Any) -> dict[str, Any]:
    resources = getattr(item, "resources", None)
    return {
        "sandbox_id": getattr(item, "sandbox_id", None),
        "name": getattr(item, "name", None),
        "status": _json_value(getattr(item, "status", None)),
        "image": getattr(item, "image", None),
        "namespace": getattr(item, "namespace", None),
        "resources": _resources_to_dict(resources),
        "timeout_secs": getattr(item, "timeout_secs", None),
    }


def _resources_to_dict(resources: Any) -> dict[str, Any]:
    if resources is None:
        return {}
    return {
        "cpus": getattr(resources, "cpus", None),
        "memory_mb": getattr(resources, "memory_mb", None),
        "disk_mb": getattr(resources, "disk_mb", None),
    }


def _json_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict, list, tuple, set)):
        return list(value)
    return value
