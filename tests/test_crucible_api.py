import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi.testclient import TestClient

from anygpu.crucible_api import create_app
from anygpu.crucible_store import CrucibleStore


ROOT = Path(__file__).resolve().parents[1]


def test_fastapi_deployment_lifecycle_tracks_deployments(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANYGPU_HOME", str(tmp_path / "state"))
    client = TestClient(create_app(CrucibleStore()))

    plan_response = client.post(
        "/deployment-plans",
        json={
            "user_id": "api-admin",
            "email": "api-admin@example.com",
            "role": "admin",
            "prompt": "Deploy Qwen 7B cheaply and expose an OpenAI compatible endpoint.",
            "source_agent": "local-api-test",
        },
    )
    assert plan_response.status_code == 201
    plan = plan_response.json()
    assert plan["status"] == "generated"
    assert plan["source"] == "local-api-test"

    blocked_response = client.post("/deployments", json={"plan_id": plan["id"]})
    assert blocked_response.status_code == 409
    assert blocked_response.json()["detail"] == "Approval required before launching GPU resources."

    approval_response = client.post(
        f"/deployment-plans/{plan['id']}/approve",
        json={"user_id": "api-admin", "email": "api-admin@example.com"},
    )
    assert approval_response.status_code == 200
    approval = approval_response.json()
    assert approval["token"].startswith("approval_token_")

    deployment_response = client.post(
        "/deployments",
        json={"plan_id": plan["id"], "approval_token": approval["token"]},
    )
    assert deployment_response.status_code == 201
    deployment = deployment_response.json()
    assert deployment["status"] == "ready"
    assert deployment["endpoint_url"].endswith("/v1/chat/completions")

    list_response = client.get("/deployments")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["deployments"]] == [deployment["id"]]

    status_response = client.get(f"/deployments/{deployment['id']}")
    assert status_response.status_code == 200
    assert status_response.json()["id"] == deployment["id"]

    health_response = client.post(f"/deployments/{deployment['id']}/health")
    assert health_response.status_code == 200
    assert health_response.json()["health_checks"][0]["status"] == "passing"

    logs_response = client.get(f"/deployments/{deployment['id']}/logs")
    assert logs_response.status_code == 200
    assert any("Health checks passed" in log["message"] for log in logs_response.json()["logs"])

    stop_response = client.post(f"/deployments/{deployment['id']}/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"


def test_fastapi_live_http_smoke_exercises_local_server(tmp_path: Path) -> None:
    port = 18973
    env = {
        "ANYGPU_HOME": str(tmp_path / "state"),
        "PYTHONPATH": str(ROOT),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "anygpu.crucible_api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env={**os.environ, **env},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as response:
                    assert response.status == 200
                    break
            except urllib.error.URLError:
                time.sleep(0.25)
        else:
            stdout, stderr = process.communicate(timeout=1)
            raise AssertionError(f"FastAPI server did not start\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")

        plan_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/deployment-plans",
            data=(
                b'{"user_id":"live-admin","email":"live-admin@example.com","role":"admin",'
                b'"prompt":"Deploy Qwen 7B cheaply from live FastAPI smoke."}'
            ),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(plan_request, timeout=5) as response:
            assert response.status == 201
            plan = json.loads(response.read().decode())
        assert plan["status"] == "generated"

        approval_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/deployment-plans/{plan['id']}/approve",
            data=b'{"user_id":"live-admin","email":"live-admin@example.com"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(approval_request, timeout=5) as response:
            assert response.status == 200
            approval = json.loads(response.read().decode())

        deploy_request = urllib.request.Request(
            f"http://127.0.0.1:{port}/deployments",
            data=json.dumps({"plan_id": plan["id"], "approval_token": approval["token"]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(deploy_request, timeout=5) as response:
            assert response.status == 201
            deployment = json.loads(response.read().decode())
        assert deployment["status"] == "ready"

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/deployments", timeout=5) as response:
            tracked = json.loads(response.read().decode())
        assert tracked["count"] == 1
        assert tracked["deployments"][0]["id"] == deployment["id"]
    finally:
        process.terminate()
        process.wait(timeout=5)
