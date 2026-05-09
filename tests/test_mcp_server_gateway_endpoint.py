from anygpu.state import edit_state
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
