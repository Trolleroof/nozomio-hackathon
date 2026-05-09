from __future__ import annotations

import importlib
import json
import sys
import types
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class FakeRunResult:
    stdout: str
    stderr: str
    exit_code: int


class FakeTensorlakeSandbox:
    created: list[dict[str, Any]] = []
    connected: list[str] = []
    terminated: list[str] = []

    def __init__(self, sandbox_id: str, name: str | None = None, image: str | None = None) -> None:
        self.id = sandbox_id
        self.sandbox_id = sandbox_id
        self.name = name
        self.status = "running"
        self.image = image

    @classmethod
    def create(cls, **kwargs: Any) -> "FakeTensorlakeSandbox":
        cls.created.append(kwargs)
        return cls("sbx-created", name=kwargs.get("name"), image=kwargs.get("image"))

    @classmethod
    def connect(cls, sandbox_ref: str) -> "FakeTensorlakeSandbox":
        cls.connected.append(sandbox_ref)
        return cls(sandbox_ref, name=sandbox_ref)

    def run(self, command: str) -> FakeRunResult:
        return FakeRunResult(stdout=f"ran {command}", stderr="", exit_code=0)

    def terminate(self) -> None:
        self.terminated.append(self.sandbox_id)
        self.status = "terminated"


def import_adapter(monkeypatch: pytest.MonkeyPatch, sandbox_cls: type[FakeTensorlakeSandbox] = FakeTensorlakeSandbox):
    tensorlake = types.ModuleType("tensorlake")
    sandbox = types.ModuleType("tensorlake.sandbox")
    sandbox.Sandbox = sandbox_cls
    tensorlake.sandbox = sandbox
    monkeypatch.setitem(sys.modules, "tensorlake", tensorlake)
    monkeypatch.setitem(sys.modules, "tensorlake.sandbox", sandbox)
    sys.modules.pop("anygpu.tensorlake_sandbox", None)
    return importlib.import_module("anygpu.tensorlake_sandbox")


def test_create_sandbox_passes_resources_and_returns_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TENSORLAKE_API_KEY", "test-token")
    FakeTensorlakeSandbox.created = []
    adapter = import_adapter(monkeypatch)

    handle = adapter.create_sandbox(
        image="python:3.12-slim",
        cpus=4,
        memory_mb=8192,
        disk_mb=20480,
        timeout_secs=600,
        name="trainer",
    )

    assert FakeTensorlakeSandbox.created == [
        {
            "image": "python:3.12-slim",
            "cpus": 4,
            "memory_mb": 8192,
            "disk_mb": 20480,
            "timeout_secs": 600,
            "name": "trainer",
        }
    ]
    assert handle == {
        "sandbox_id": "sbx-created",
        "name": "trainer",
        "status": "running",
        "image": "python:3.12-slim",
        "resources": {
            "cpus": 4,
            "memory_mb": 8192,
            "disk_mb": 20480,
            "timeout_secs": 600,
        },
    }


def test_run_command_connects_by_id_or_name_and_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TENSORLAKE_API_KEY", "test-token")
    FakeTensorlakeSandbox.connected = []
    adapter = import_adapter(monkeypatch)

    by_id = adapter.run_command(sandbox_id="sbx-123", command="python train.py")
    by_name = adapter.run_command(name="trainer", command="echo ready")

    assert FakeTensorlakeSandbox.connected == ["sbx-123", "trainer"]
    assert by_id == {"stdout": "ran python train.py", "stderr": "", "exit_code": 0}
    assert by_name == {"stdout": "ran echo ready", "stderr": "", "exit_code": 0}


def test_terminate_sandbox_connects_and_terminates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TENSORLAKE_API_KEY", "test-token")
    FakeTensorlakeSandbox.connected = []
    FakeTensorlakeSandbox.terminated = []
    adapter = import_adapter(monkeypatch)

    result = adapter.terminate_sandbox(sandbox_id="sbx-123")

    assert FakeTensorlakeSandbox.connected == ["sbx-123"]
    assert FakeTensorlakeSandbox.terminated == ["sbx-123"]
    assert result == {"sandbox_id": "sbx-123", "status": "terminated"}


def test_missing_api_key_fails_before_importing_tensorlake_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TENSORLAKE_API_KEY", raising=False)
    sys.modules.pop("anygpu.tensorlake_sandbox", None)
    sys.modules.pop("tensorlake", None)
    sys.modules.pop("tensorlake.sandbox", None)
    adapter = importlib.import_module("anygpu.tensorlake_sandbox")

    class TensorlakeImportBlocker:
        def find_spec(self, fullname: str, *_args: Any) -> None:
            if fullname == "tensorlake" or fullname.startswith("tensorlake."):
                raise AssertionError("tensorlake SDK should not be imported without TENSORLAKE_API_KEY")
            return None

    blocker = TensorlakeImportBlocker()
    sys.meta_path.insert(0, blocker)
    try:
        with pytest.raises(RuntimeError, match="TENSORLAKE_API_KEY"):
            adapter.create_sandbox(image="python:3.12-slim", name="trainer")
    finally:
        sys.meta_path.remove(blocker)


def test_crucible_mcp_exposes_tensorlake_sandbox_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TENSORLAKE_API_KEY", "test-token")
    from anygpu.crucible_mcp import handle_tool_call, list_tools

    calls: list[tuple[str, dict[str, Any]]] = []
    fake_adapter = types.ModuleType("anygpu.tensorlake_sandbox")
    fake_adapter.create_sandbox = lambda **kwargs: calls.append(("create", kwargs)) or {"sandbox_id": "sbx-123"}
    fake_adapter.run_command = (
        lambda **kwargs: calls.append(("run", kwargs)) or {"stdout": "ok\n", "stderr": "", "exit_code": 0}
    )
    fake_adapter.terminate_sandbox = (
        lambda **kwargs: calls.append(("terminate", kwargs)) or {"sandbox_id": "sbx-123", "status": "terminated"}
    )
    fake_adapter.list_sandboxes = lambda: calls.append(("list", {})) or [{"sandbox_id": "sbx-123", "status": "running"}]
    monkeypatch.setitem(sys.modules, "anygpu.tensorlake_sandbox", fake_adapter)

    tool_names = {tool["name"] for tool in list_tools()}
    assert {
        "crucible_create_tensorlake_sandbox",
        "crucible_run_tensorlake_command",
        "crucible_terminate_tensorlake_sandbox",
        "crucible_list_tensorlake_sandboxes",
    } <= tool_names

    created = handle_tool_call(
        object(),
        "crucible_create_tensorlake_sandbox",
        {"image": "python:3.12-slim", "cpus": 2, "memoryMb": 2048, "diskMb": 10240, "timeoutSecs": 120, "name": "trainer"},
    )
    ran = handle_tool_call(
        object(),
        "crucible_run_tensorlake_command",
        {"sandboxId": "sbx-123", "command": "python train.py", "timeoutSecs": 30},
    )
    listed = handle_tool_call(object(), "crucible_list_tensorlake_sandboxes", {})
    terminated = handle_tool_call(object(), "crucible_terminate_tensorlake_sandbox", {"sandboxId": "sbx-123"})

    assert created["content"] == {"sandbox_id": "sbx-123"}
    assert ran["content"]["stdout"] == "ok\n"
    assert listed["content"] == [{"sandbox_id": "sbx-123", "status": "running"}]
    assert terminated["content"]["status"] == "terminated"
    assert calls == [
        (
            "create",
            {
                "image": "python:3.12-slim",
                "cpus": 2,
                "memory_mb": 2048,
                "disk_mb": 10240,
                "timeout_secs": 120,
                "name": "trainer",
            },
        ),
        ("run", {"sandbox_id": "sbx-123", "name": None, "command": "python train.py", "args": None, "timeout": 30}),
        ("list", {}),
        ("terminate", {"sandbox_id": "sbx-123", "name": None}),
    ]


def test_provider_capabilities_include_tensorlake(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("TENSORLAKE_API_KEY", "test-token")
    from anygpu.crucible import list_provider_capabilities
    from anygpu.crucible_store import CrucibleStore

    capabilities = list_provider_capabilities(CrucibleStore())

    tensorlake = {item["provider"]: item for item in capabilities}["Tensorlake"]
    assert tensorlake["status"] == "configured"
    assert tensorlake["supports_deploy"] is True
    assert tensorlake["supports_openai_endpoint"] is False
    assert tensorlake["credentials_required"] == ["TENSORLAKE_API_KEY"]


def test_fastmcp_tensorlake_tools_delegate_to_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    fake_adapter = types.ModuleType("anygpu.tensorlake_sandbox")
    fake_adapter.create_sandbox = lambda **kwargs: calls.append(("create", kwargs)) or {"sandbox_id": "sbx-fastmcp"}
    fake_adapter.run_command = (
        lambda **kwargs: calls.append(("run", kwargs)) or {"stdout": "ok", "stderr": "", "exit_code": 0}
    )
    fake_adapter.terminate_sandbox = (
        lambda **kwargs: calls.append(("terminate", kwargs)) or {"sandbox_id": "sbx-fastmcp", "status": "terminated"}
    )
    fake_adapter.list_sandboxes = lambda: calls.append(("list", {})) or [{"sandbox_id": "sbx-fastmcp"}]
    monkeypatch.setitem(sys.modules, "anygpu.tensorlake_sandbox", fake_adapter)

    fastmcp_module = types.ModuleType("mcp.server.fastmcp")

    class FakeFastMCP:
        def __init__(self, _name: str) -> None:
            pass

        def tool(self):
            def decorate(fn):
                fn.fn = fn
                return fn

            return decorate

        def run(self) -> None:
            pass

    fastmcp_module.FastMCP = FakeFastMCP
    monkeypatch.setitem(sys.modules, "mcp", types.ModuleType("mcp"))
    monkeypatch.setitem(sys.modules, "mcp.server", types.ModuleType("mcp.server"))
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_module)
    sys.modules.pop("mcp_server.server", None)

    from mcp_server import server

    created = json.loads(server.create_tensorlake_sandbox(name="trainer", memory_mb=2048))
    ran = json.loads(server.run_tensorlake_command(sandbox_id="sbx-fastmcp", command="echo ok"))
    listed = json.loads(server.list_tensorlake_sandboxes())
    terminated = json.loads(server.terminate_tensorlake_sandbox(sandbox_id="sbx-fastmcp"))

    assert created == {"sandbox_id": "sbx-fastmcp"}
    assert ran["exit_code"] == 0
    assert listed == [{"sandbox_id": "sbx-fastmcp"}]
    assert terminated["status"] == "terminated"
    assert calls == [
        (
            "create",
            {
                "image": "tensorlake/ubuntu-minimal",
                "cpus": 1.0,
                "memory_mb": 2048,
                "disk_mb": 10240,
                "timeout_secs": 300,
                "name": "trainer",
            },
        ),
        ("run", {"sandbox_id": "sbx-fastmcp", "name": None, "command": "echo ok", "args": None, "timeout": None}),
        ("list", {}),
        ("terminate", {"sandbox_id": "sbx-fastmcp", "name": None}),
    ]
