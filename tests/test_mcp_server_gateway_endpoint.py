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


def test_public_gateway_response_hides_upstream_secrets() -> None:
    safe = server._safe_gateway_response(
        {
            "base_url": "http://127.0.0.1:8765/v1",
            "model": "local-chat",
            "upstream_url": "http://203.0.113.9:8000/v1/chat/completions",
            "api_key": "public-nope",
            "upstream_api_key": "upstream-nope",
        }
    )

    assert safe == {
        "base_url": "http://127.0.0.1:8765/v1",
        "model": "local-chat",
        "authentication": "handled_by_server_proxy",
    }


def test_public_mcp_credit_helper_requires_user_in_public_mode(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "anygpu"))
    monkeypatch.setenv("CRUCIBLE_PUBLIC_MCP_REQUIRE_CREDITS", "true")
    monkeypatch.setenv("CRUCIBLE_PUBLIC_MCP_STARTING_CREDITS", "5")

    try:
        server._maybe_consume_public_credit("deploy_cheapest", None)
    except RuntimeError as exc:
        assert str(exc) == "public_user_id is required for this public MCP server."
    else:
        raise AssertionError("public mode should require a public_user_id")

    result = server._maybe_consume_public_credit("deploy_cheapest", "install-123")

    assert result is not None
    assert result["account"]["remaining_runs"] == 4
    assert result["account"]["policy"]["secret_exposure"] == "server_only"
