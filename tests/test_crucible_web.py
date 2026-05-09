import http.client
import json
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from anygpu.crucible_web import make_server


@contextmanager
def web_server(tmp_path: Path):
    os.environ["ANYGPU_HOME"] = str(tmp_path / "state")
    server = make_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(server, method: str, path: str, body: dict | None = None, cookie: str | None = None):
    host, port = server.server_address
    conn = http.client.HTTPConnection(host, port, timeout=10)
    headers = {}
    payload = None
    if body is not None:
        payload = json.dumps(body)
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    conn.request(method, path, payload, headers)
    response = conn.getresponse()
    data = response.read().decode()
    conn.close()
    return response.status, dict(response.headers), data


def test_public_auth_and_protected_dashboard(tmp_path: Path) -> None:
    with web_server(tmp_path) as server:
        status, _, landing = request(server, "GET", "/")
        assert status == 200
        assert "Crucible Compute" in landing

        status, _, body = request(server, "GET", "/dashboard")
        assert status == 401
        assert "Sign in required" in body

        status, headers, signup = request(
            server,
            "POST",
            "/api/signup",
            {"email": "judge@example.com", "password": "pw", "role": "admin"},
        )
        assert status == 200
        assert "judge@example.com" in signup
        cookie = headers["Set-Cookie"].split(";", 1)[0]

        status, _, dashboard = request(server, "GET", "/dashboard", cookie=cookie)
        assert status == 200
        assert "Active deployments" in dashboard
        assert "Provider status" in dashboard
        assert "Context used by agent" in dashboard


def test_plan_approval_deploy_pages_and_api_flow(tmp_path: Path) -> None:
    with web_server(tmp_path) as server:
        status, headers, signup = request(
            server,
            "POST",
            "/api/signup",
            {"email": "admin@example.com", "password": "pw", "role": "admin"},
        )
        assert status == 200
        user = json.loads(signup)
        cookie = headers["Set-Cookie"].split(";", 1)[0]

        status, _, plan_body = request(
            server,
            "POST",
            "/api/deployment-plans",
            {"userId": user["id"], "prompt": "Deploy Qwen 7B cheaply"},
            cookie=cookie,
        )
        plan = json.loads(plan_body)
        assert status == 200
        assert plan["approval_required"] is True

        status, _, blocked_body = request(server, "POST", f"/api/deployments?planId={plan['id']}", cookie=cookie)
        blocked = json.loads(blocked_body)
        assert status == 403
        assert blocked["error"] == "Approval required before launching GPU resources."

        status, _, approval_body = request(
            server,
            "POST",
            f"/api/deployment-plans/{plan['id']}/approval",
            {"userId": user["id"]},
            cookie=cookie,
        )
        approval = json.loads(approval_body)
        assert status == 200

        status, _, deployment_body = request(
            server,
            "POST",
            f"/api/deployments?planId={plan['id']}&approvalToken={approval['token']}",
            cookie=cookie,
        )
        deployment = json.loads(deployment_body)
        assert status == 200
        assert deployment["status"] == "ready"

        status, _, page = request(server, "GET", f"/deployments/{deployment['id']}", cookie=cookie)
        assert status == 200
        assert "Health checks" in page
        assert "Playground" in page
        assert "Stop deployment" in page

        status, _, stopped_body = request(server, "POST", f"/api/deployments/{deployment['id']}/stop", cookie=cookie)
        stopped = json.loads(stopped_body)
        assert status == 200
        assert stopped["status"] == "stopped"


def test_context_providers_and_agent_pages_are_visible(tmp_path: Path) -> None:
    with web_server(tmp_path) as server:
        status, headers, _ = request(
            server,
            "POST",
            "/api/signup",
            {"email": "judge@example.com", "password": "pw", "role": "admin"},
        )
        cookie = headers["Set-Cookie"].split(";", 1)[0]

        for path, expected in [
            ("/providers", "Live deploy supported"),
            ("/context", "Context snippets used in agent decisions"),
            ("/agent", "crucible_plan_deployment"),
        ]:
            status, _, body = request(server, "GET", path, cookie=cookie)
            assert status == 200
            assert expected in body
