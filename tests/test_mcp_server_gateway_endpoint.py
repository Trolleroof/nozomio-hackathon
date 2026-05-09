from anygpu.state import edit_state
from anygpu.state import load_state
from mcp_server.models import DeployedInstance
from mcp_server import server


def test_mcp_endpoint_prefers_main_anygpu_gateway_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "anygpu"))
    with edit_state() as state:
        state["deployments"]["local-chat"] = {
            "name": "local-chat",
            "health": "healthy",
            "created_at": "2026-05-09T20:00:00Z",
            "gateway": {
                "base_url": "http://127.0.0.1:8765/v1",
                "model": "local-chat",
                "chat_completions_url": "http://127.0.0.1:8765/v1/chat/completions",
            },
            "upstream_url": "http://127.0.0.1:19600/v1/chat/completions",
        }

    endpoint = server._anygpu_gateway_endpoint()

    assert endpoint == {
        "base_url": "http://127.0.0.1:8765/v1",
        "model": "local-chat",
        "upstream_url": "http://127.0.0.1:19600/v1/chat/completions",
    }


def test_mcp_registers_deployment_as_real_gateway_route(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "anygpu"))
    instance = DeployedInstance(
        provider="runpod",
        instance_id="pod-123",
        gpu_type="A40",
        price_per_hr=0.44,
        endpoint_url="http://203.0.113.9:8000/v1",
        api_key="upstream-key",
        deployed_at=1.0,
        region="global",
    )

    endpoint = server._register_anygpu_gateway_route(instance)
    state = load_state()
    deployment = state["deployments"]["local-chat"]
    route = deployment["routes"][0]

    assert endpoint == {
        "base_url": "http://127.0.0.1:8765/v1",
        "model": "local-chat",
        "chat_completions_url": "http://127.0.0.1:8765/v1/chat/completions",
        "upstream_url": "http://203.0.113.9:8000/v1/chat/completions",
    }
    assert deployment["provider"] == "runpod"
    assert deployment["runtime"] == "vllm"
    assert deployment["health"] == "healthy"
    assert route["simulated"] is False
    assert route["runtime_url"] == "http://203.0.113.9:8000"
    assert route["upstream_api_key"] == "upstream-key"
