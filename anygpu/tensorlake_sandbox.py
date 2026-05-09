from __future__ import annotations

import importlib
import os
import shlex
from collections.abc import Iterable
from typing import Any

DEFAULT_IMAGE = "tensorlake/ubuntu-minimal"
DEFAULT_CPUS = 1.0
DEFAULT_MEMORY_MB = 1024
DEFAULT_DISK_MB = 10240
DEFAULT_TIMEOUT_SECS = 300
DEFAULT_VCPU_HOST_CPUS = 1.0
DEFAULT_VCPU_HOST_MEMORY_MB = 2048
DEFAULT_VCPU_HOST_DISK_MB = 10240
DEFAULT_VCPU_HOST_TIMEOUT_SECS = 3600


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


def create_vcpu_host(
    *,
    name: str,
    image: str = DEFAULT_IMAGE,
    cpus: float = DEFAULT_VCPU_HOST_CPUS,
    memory_mb: int = DEFAULT_VCPU_HOST_MEMORY_MB,
    disk_mb: int = DEFAULT_VCPU_HOST_DISK_MB,
    timeout_secs: int = DEFAULT_VCPU_HOST_TIMEOUT_SECS,
) -> dict[str, Any]:
    """Create a CPU-only sandbox intended for autonomous site or tool hosting."""
    handle = create_sandbox(
        image=image,
        cpus=cpus,
        memory_mb=memory_mb,
        disk_mb=disk_mb,
        timeout_secs=timeout_secs,
        name=name,
    )
    handle["kind"] = "vcpu_host"
    handle["public_hostname"] = _public_hostname(str(handle.get("name") or handle["sandbox_id"]))
    return handle


def run_vcpu_command(
    *,
    command: str,
    sandbox_id: str | None = None,
    name: str | None = None,
    args: list[str] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Run a command inside a CPU sandbox."""
    return run_command(sandbox_id=sandbox_id, name=name, command=command, args=args, timeout=timeout)


def start_site(
    *,
    command: str,
    port: int,
    sandbox_id: str | None = None,
    name: str | None = None,
    working_dir: str | None = None,
    public: bool = True,
) -> dict[str, Any]:
    """Start a long-running site command in the background and optionally expose its port."""
    sandbox = _connect(sandbox_id=sandbox_id, name=name)
    resolved_id = getattr(sandbox, "sandbox_id", sandbox_id or name)
    process: dict[str, Any]
    if hasattr(sandbox, "start_process"):
        started = sandbox.start_process(command, working_dir=working_dir)
        process = {
            "process_id": getattr(started, "process_id", getattr(started, "id", None)),
            "status": _json_value(getattr(started, "status", None)),
            "command": command,
        }
    else:
        shell_command = _background_site_command(command, port=port, working_dir=working_dir)
        run_result = run_vcpu_command(sandbox_id=sandbox_id, name=name, command=shell_command)
        process = {"command": shell_command, "run": run_result}
    result: dict[str, Any] = {
        "sandbox_id": resolved_id,
        "name": name,
        "port": port,
        "command": command,
        "process": process,
    }
    if public:
        exposure = expose_site_port(sandbox_id=sandbox_id, name=name, port=port, public=True)
        result["sandbox_id"] = exposure.get("sandbox_id") or sandbox_id
        result["name"] = exposure.get("name") or name
        result["public_url"] = exposure.get("public_url")
        result["exposure"] = exposure
    return result


def expose_site_port(
    *,
    port: int,
    sandbox_id: str | None = None,
    name: str | None = None,
    public: bool = True,
) -> dict[str, Any]:
    """Expose a sandbox port through Tensorlake networking."""
    ref = sandbox_id or name
    if not ref:
        raise ValueError("sandbox_id or name is required.")
    if port <= 0:
        raise ValueError("port must be a positive integer.")
    sandbox = _connect(sandbox_id=sandbox_id, name=name)
    if not hasattr(sandbox, "update"):
        raise RuntimeError("Tensorlake Sandbox.update is required to expose site ports.")
    response = sandbox.update(exposed_ports=[port], allow_unauthenticated_access=public)
    sandbox_url = getattr(response, "sandbox_url", None) or getattr(sandbox, "sandbox_url", None)
    return {
        "sandbox_id": getattr(response, "sandbox_id", None) or getattr(response, "id", None) or sandbox_id or ref,
        "name": getattr(response, "name", None) or name,
        "status": _json_value(getattr(response, "status", None)),
        "port": port,
        "public": public,
        "exposed_ports": getattr(response, "exposed_ports", [port]),
        "sandbox_url": sandbox_url,
        "public_url": _port_public_url(sandbox_url, port),
        "resources": _resources_to_dict(getattr(response, "resources", None)),
    }


def get_site_status(*, sandbox_id: str | None = None, name: str | None = None, port: int | None = None) -> dict[str, Any]:
    """Return sandbox status plus derived public URL metadata for a hosted site."""
    sandbox = _connect(sandbox_id=sandbox_id, name=name)
    resolved_id = getattr(sandbox, "sandbox_id", sandbox_id or name)
    sandbox_url = getattr(sandbox, "sandbox_url", None) or getattr(sandbox, "url", None)
    return {
        "sandbox_id": resolved_id,
        "name": getattr(sandbox, "name", name),
        "status": _json_value(getattr(sandbox, "status", None)),
        "image": getattr(sandbox, "image", None),
        "port": port,
        "sandbox_url": sandbox_url,
        "public_url": _port_public_url(sandbox_url, port) if port is not None else None,
        "resources": _resources_to_dict(getattr(sandbox, "resources", None)),
    }


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


def _background_site_command(command: str, *, port: int, working_dir: str | None = None) -> str:
    parts: list[str] = ["set -e"]
    if working_dir:
        parts.append(f"cd {shlex.quote(working_dir)}")
    log_path = f"/tmp/anygpu-site-{port}.log"
    parts.append(f"nohup {command} > {shlex.quote(log_path)} 2>&1 &")
    parts.append("echo $!")
    return " && ".join(parts)


def _public_hostname(value: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    return f"{safe or 'sandbox'}.sandbox.tensorlake.ai"


def _port_public_url(sandbox_url: str | None, port: int | None) -> str | None:
    if not sandbox_url or port is None:
        return None
    normalized = sandbox_url.rstrip("/")
    if "://" not in normalized:
        return None
    scheme, rest = normalized.split("://", 1)
    return f"{scheme}://{port}-{rest}"


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
