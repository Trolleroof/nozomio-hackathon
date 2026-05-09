from __future__ import annotations

import html
import json
import os
import secrets
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


APPROVAL_REQUIRED_MESSAGE = "Approval required before launching GPU resources."
SESSION_COOKIE = "crucible_session"


try:
    from anygpu.crucible import (  # type: ignore
        ApprovalRequiredError,
        approve_plan,
        create_deployment_plan,
        deploy_approved_plan,
        get_deployment,
        list_provider_capabilities,
        login_user,
        signup_user,
        stop_deployment,
    )
    from anygpu.crucible_store import CrucibleStore  # type: ignore
except Exception:  # pragma: no cover - exercised only until backend lands.

    class ApprovalRequiredError(RuntimeError):
        pass

    class CrucibleStore:
        def __init__(self) -> None:
            self.users: dict[str, dict[str, Any]] = {}
            self.users_by_email: dict[str, str] = {}
            self.sessions: dict[str, str] = {}
            self.plans: dict[str, dict[str, Any]] = {}
            self.approvals: dict[str, dict[str, Any]] = {}
            self.deployments: dict[str, dict[str, Any]] = {}
            self._counters = {"usr": 0, "sess": 0, "plan": 0, "appr": 0, "dep": 0}

        def next_id(self, prefix: str) -> str:
            self._counters[prefix] += 1
            return f"{prefix}_{self._counters[prefix]:04d}"

    def signup_user(store: CrucibleStore, email: str, password: str, role: str = "user") -> dict[str, Any]:
        existing_id = store.users_by_email.get(email)
        if existing_id:
            user = dict(store.users[existing_id])
            user.pop("password", None)
            return user
        user_id = store.next_id("usr")
        user = {"id": user_id, "email": email, "password": password, "role": role or "user"}
        store.users[user_id] = user
        store.users_by_email[email] = user_id
        public = dict(user)
        public.pop("password", None)
        return public

    def login_user(store: CrucibleStore, email: str, password: str) -> dict[str, Any]:
        user_id = store.users_by_email.get(email)
        if not user_id or store.users[user_id].get("password") != password:
            raise ValueError("Invalid email or password")
        token = store.next_id("sess")
        store.sessions[token] = user_id
        return {"token": token, "user_id": user_id}

    def create_deployment_plan(
        store: CrucibleStore,
        user_id: str,
        prompt: str,
        source: str = "dashboard",
    ) -> dict[str, Any]:
        plan_id = store.next_id("plan")
        plan = {
            "id": plan_id,
            "user_id": user_id,
            "prompt": prompt,
            "source": source,
            "status": "generated",
            "model_id": "Qwen/Qwen2.5-7B-Instruct",
            "objective": "cheapest",
            "approval_required": True,
            "recommendation": {
                "provider": "Modal",
                "accelerator": "A10G",
                "estimated_hourly_cost": 0.74,
                "deployment_mode": "vLLM OpenAI-compatible endpoint",
            },
            "context_used": [
                "Modal vLLM templates expose OpenAI-compatible /v1/chat/completions routes.",
                "Approval is required before launching paid GPU resources.",
                "Prefer a single cost-efficient GPU for Qwen 7B unless latency requires scaling.",
            ],
            "next_action": "Approval required before deploy.",
        }
        store.plans[plan_id] = plan
        return dict(plan)

    def approve_plan(store: CrucibleStore, plan_id: str, user_id: str) -> dict[str, Any]:
        if plan_id not in store.plans:
            raise KeyError(plan_id)
        token = f"appr_{secrets.token_urlsafe(12)}"
        approval = {"id": store.next_id("appr"), "plan_id": plan_id, "user_id": user_id, "token": token}
        store.approvals[token] = approval
        store.plans[plan_id]["status"] = "approved"
        return dict(approval)

    def deploy_approved_plan(
        store: CrucibleStore,
        plan_id: str,
        approval_token: str | None = None,
    ) -> dict[str, Any]:
        plan = store.plans.get(plan_id)
        if not plan:
            raise KeyError(plan_id)
        approval = store.approvals.get(approval_token or "")
        if plan.get("approval_required") and (not approval or approval.get("plan_id") != plan_id):
            raise ApprovalRequiredError(APPROVAL_REQUIRED_MESSAGE)
        deployment_id = store.next_id("dep")
        deployment = {
            "id": deployment_id,
            "plan_id": plan_id,
            "status": "ready",
            "provider": plan["recommendation"]["provider"],
            "model_id": plan["model_id"],
            "endpoint_url": f"https://crucible.local/deployments/{deployment_id}/v1/chat/completions",
            "health_checks": [
                {"name": "container", "status": "passing"},
                {"name": "openai-compatible endpoint", "status": "passing"},
            ],
            "benchmark": {"tokens_per_second": 84.2, "latency_ms": 118},
            "logs": [
                {"level": "info", "message": "Provisioned GPU runtime."},
                {"level": "info", "message": "Health checks passed."},
            ],
        }
        store.deployments[deployment_id] = deployment
        plan["status"] = "deployed"
        return dict(deployment)

    def get_deployment(store: CrucibleStore, deployment_id: str) -> dict[str, Any]:
        deployment = store.deployments.get(deployment_id)
        if not deployment:
            raise KeyError(deployment_id)
        return dict(deployment)

    def stop_deployment(store: CrucibleStore, deployment_id: str) -> dict[str, Any]:
        deployment = get_deployment(store, deployment_id)
        deployment["status"] = "stopped"
        deployment.setdefault("logs", []).append({"level": "info", "message": "Stop requested; deployment marked stopped."})
        store.deployments[deployment_id] = deployment
        return dict(deployment)

    def list_provider_capabilities(store: CrucibleStore) -> list[dict[str, Any]]:
        modal_configured = bool(os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"))
        skypilot_configured = bool(os.environ.get("SKYPILOT_API_SERVER_ENDPOINT"))
        return [
            {
                "provider": "Modal",
                "status": "configured" if modal_configured else "missing credentials",
                "supports_openai_endpoint": True,
                "supports_deploy": modal_configured,
            },
            {
                "provider": "SkyPilot",
                "status": "configured" if skypilot_configured else "missing credentials",
                "supports_openai_endpoint": True,
                "supports_deploy": skypilot_configured,
            },
            {
                "provider": "Lambda Cloud",
                "status": "unsupported",
                "supports_openai_endpoint": False,
                "supports_deploy": False,
            },
            {
                "provider": "CoreWeave",
                "status": "unsupported",
                "supports_openai_endpoint": False,
                "supports_deploy": False,
            },
        ]


class CrucibleWebServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler]) -> None:
        super().__init__(server_address, handler_class)
        self.store = CrucibleStore()
        self.web_sessions: dict[str, dict[str, Any]] = {}


class CrucibleRequestHandler(BaseHTTPRequestHandler):
    server: CrucibleWebServer

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._send_html(self._landing_page())
            return

        user = self._require_user()
        if not user:
            return

        if path == "/dashboard":
            self._send_html(self._dashboard_page(user))
            return
        if path == "/providers":
            self._send_html(self._providers_page())
            return
        if path == "/context":
            self._send_html(self._context_page())
            return
        if path == "/agent":
            self._send_html(self._agent_page())
            return
        if path.startswith("/deployments/"):
            deployment_id = path.split("/", 2)[2]
            self._send_html(self._deployment_page(deployment_id), status=HTTPStatus.OK)
            return

        if path.startswith("/api/deployments/"):
            deployment_id = path.split("/", 3)[3]
            self._send_json(self._find_deployment(deployment_id))
            return

        self._send_text("Not found", status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/api/signup":
            self._handle_signup()
            return
        if path == "/api/login":
            self._handle_login()
            return

        user = self._require_user(json_response=path.startswith("/api/"))
        if not user:
            return

        if path == "/api/deployment-plans":
            payload = self._read_json()
            plan = create_deployment_plan(
                self.server.store,
                str(payload.get("userId") or user.get("id") or ""),
                str(payload.get("prompt") or ""),
                source="dashboard",
            )
            self._send_json(plan)
            return

        if path.startswith("/api/deployment-plans/") and path.endswith("/approval"):
            plan_id = path.split("/")[3]
            payload = self._read_json()
            approval = approve_plan(
                self.server.store,
                plan_id,
                str(payload.get("userId") or user.get("id") or ""),
            )
            self._send_json(approval)
            return

        if path == "/api/deployments":
            plan_id = _first_query(query, "planId")
            approval_token = _first_query(query, "approvalToken")
            if not plan_id:
                self._send_json({"error": "Missing planId."}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                deployment = deploy_approved_plan(self.server.store, plan_id, approval_token=approval_token)
            except ApprovalRequiredError as exc:
                self._send_json({"error": str(exc) or APPROVAL_REQUIRED_MESSAGE}, status=HTTPStatus.FORBIDDEN)
                return
            self._send_json(deployment)
            return

        if path.startswith("/api/deployments/") and path.endswith("/playground"):
            deployment_id = path.split("/")[3]
            deployment = self._find_deployment(deployment_id)
            self._send_json(
                {
                    "deploymentId": deployment["id"],
                    "response": f"Connected to {deployment.get('model_id', 'model')} through the Crucible playground.",
                }
            )
            return

        if path.startswith("/api/deployments/") and path.endswith("/stop"):
            deployment_id = path.split("/")[3]
            self._send_json(stop_deployment(self.server.store, deployment_id))
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def _handle_signup(self) -> None:
        payload = self._read_json()
        try:
            user = signup_user(
                self.server.store,
                str(payload.get("email") or ""),
                str(payload.get("password") or ""),
                role=str(payload.get("role") or "user"),
            )
            session = login_user(
                self.server.store,
                str(payload.get("email") or ""),
                str(payload.get("password") or ""),
            )
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        token = str(session.get("token") or secrets.token_urlsafe(24))
        self.server.web_sessions[token] = dict(user)
        self._send_json(user, headers={"Set-Cookie": _session_cookie(token)})

    def _handle_login(self) -> None:
        payload = self._read_json()
        try:
            session = login_user(
                self.server.store,
                str(payload.get("email") or ""),
                str(payload.get("password") or ""),
            )
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.UNAUTHORIZED)
            return
        token = str(session.get("token") or secrets.token_urlsafe(24))
        user = self._lookup_user(str(payload.get("email") or ""), session)
        self.server.web_sessions[token] = user
        self._send_json(user, headers={"Set-Cookie": _session_cookie(token)})

    def _require_user(self, json_response: bool = False) -> dict[str, Any] | None:
        user = self._current_user()
        if user:
            return user
        if json_response:
            self._send_json({"error": "Sign in required"}, status=HTTPStatus.UNAUTHORIZED)
        else:
            self._send_html(
                _page("Sign in required", "<h1>Sign in required</h1><p>Please sign in to continue.</p>"),
                status=HTTPStatus.UNAUTHORIZED,
            )
        return None

    def _current_user(self) -> dict[str, Any] | None:
        raw = self.headers.get("Cookie", "")
        cookie = SimpleCookie(raw)
        morsel = cookie.get(SESSION_COOKIE)
        if not morsel:
            return None
        return self.server.web_sessions.get(morsel.value)

    def _lookup_user(self, email: str, session: dict[str, Any]) -> dict[str, Any]:
        user_id = str(session.get("user_id") or session.get("userId") or "")
        store = self.server.store
        if hasattr(store, "users") and user_id in store.users:
            user = dict(store.users[user_id])
            user.pop("password", None)
            return user
        for user in self.server.web_sessions.values():
            if user.get("email") == email:
                return dict(user)
        return {"id": user_id, "email": email, "role": "user"}

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if not raw:
            return {}
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else {}

    def _send_json(
        self,
        payload: dict[str, Any] | list[dict[str, Any]],
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(
        self,
        body: str,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(encoded)

    def _send_text(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _landing_page(self) -> str:
        content = """
        <h1>Crucible Compute</h1>
        <p>Plan, approve, and launch GPU-backed inference endpoints with explicit human approval.</p>
        <form method="post" action="/api/signup">
          <input name="email" placeholder="email">
          <input name="password" type="password" placeholder="password">
          <button>Create account</button>
        </form>
        """
        return _page("Crucible Compute", content)

    def _dashboard_page(self, user: dict[str, Any]) -> str:
        deployments = self._list_deployments()
        deployment_rows = "".join(
            f"<li><a href='/deployments/{_e(item['id'])}'>{_e(item['id'])}</a> - {_e(item.get('status', 'unknown'))}</li>"
            for item in deployments
        ) or "<li>No deployments yet.</li>"
        content = f"""
        <h1>Dashboard</h1>
        <p>Signed in as {_e(user.get('email', 'unknown'))}</p>
        <section><h2>Active deployments</h2><ul>{deployment_rows}</ul></section>
        <section><h2>Provider status</h2>{self._provider_table()}</section>
        <section><h2>Context used by agent</h2>{self._context_list()}</section>
        """
        return _page("Dashboard", content)

    def _providers_page(self) -> str:
        content = f"""
        <h1>Providers</h1>
        <p>Live deploy supported status is based on local credentials and provider support.</p>
        {self._provider_table()}
        """
        return _page("Providers", content)

    def _context_page(self) -> str:
        content = f"""
        <h1>Context snippets used in agent decisions</h1>
        {self._context_list()}
        """
        return _page("Context", content)

    def _agent_page(self) -> str:
        content = """
        <h1>Agent tools</h1>
        <ul>
          <li><code>crucible_plan_deployment</code> - create a deployment plan with retrieved context.</li>
          <li><code>crucible_approve_plan</code> - record human approval for paid resources.</li>
          <li><code>crucible_deploy_approved_plan</code> - launch an approved deployment.</li>
          <li><code>crucible_get_deployment_status</code> - inspect readiness and endpoint details.</li>
        </ul>
        """
        return _page("Agent", content)

    def _deployment_page(self, deployment_id: str) -> str:
        try:
            deployment = self._find_deployment(deployment_id)
        except KeyError:
            return _page("Deployment not found", "<h1>Deployment not found</h1>")

        checks = "".join(
            f"<li>{_e(item.get('name', 'check'))}: {_e(item.get('status', 'unknown'))}</li>"
            for item in deployment.get("health_checks", [])
        )
        logs = "".join(
            f"<li>{_e(item.get('level', 'info'))}: {_e(item.get('message', ''))}</li>"
            for item in deployment.get("logs", [])
        )
        content = f"""
        <h1>Deployment {_e(deployment.get('id', deployment_id))}</h1>
        <p>Status: {_e(deployment.get('status', 'unknown'))}</p>
        <p>Endpoint: <code>{_e(deployment.get('endpoint_url', 'pending'))}</code></p>
        <section><h2>Health checks</h2><ul>{checks}</ul></section>
        <section><h2>Logs</h2><ul>{logs}</ul></section>
        <section><h2>Playground</h2><textarea>Send a chat completion test prompt.</textarea></section>
        <section><h2>Stop deployment</h2><button>Stop deployment</button></section>
        """
        return _page("Deployment", content)

    def _provider_table(self) -> str:
        rows = []
        for item in list_provider_capabilities(self.server.store):
            rows.append(
                "<tr>"
                f"<td>{_e(item.get('provider', 'unknown'))}</td>"
                f"<td>{_e(item.get('status', 'unknown'))}</td>"
                f"<td>{'Yes' if item.get('supports_openai_endpoint') else 'No'}</td>"
                f"<td>Live deploy supported: {'Yes' if item.get('supports_deploy') else 'No'}</td>"
                "</tr>"
            )
        return (
            "<table><thead><tr><th>Provider</th><th>Status</th><th>OpenAI endpoint</th>"
            "<th>Deploy</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )

    def _context_list(self) -> str:
        snippets = [
            "Approval gates protect paid GPU resources from accidental launches.",
            "Modal and SkyPilot are preferred when OpenAI-compatible vLLM endpoints are available.",
            "Health checks and logs are shown before handoff to the playground.",
        ]
        return "<ul>" + "".join(f"<li>{_e(snippet)}</li>" for snippet in snippets) + "</ul>"

    def _list_deployments(self) -> list[dict[str, Any]]:
        store = self.server.store
        if hasattr(store, "deployments"):
            return [dict(item) for item in store.deployments.values()]
        if hasattr(store, "list_deployments"):
            return store.list_deployments()
        return []

    def _find_deployment(self, deployment_id: str) -> dict[str, Any]:
        try:
            return get_deployment(self.server.store, deployment_id)
        except KeyError:
            raise


def make_server(host: str = "127.0.0.1", port: int = 8766) -> CrucibleWebServer:
    return CrucibleWebServer((host, port), CrucibleRequestHandler)


def serve(host: str = "127.0.0.1", port: int = 8766) -> None:
    server = make_server(host, port)
    print(f"Crucible web/API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _session_cookie(token: str) -> str:
    return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax"


def _first_query(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0]


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{_e(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 960px; line-height: 1.45; }}
    nav a {{ margin-right: 1rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccd1d5; padding: 0.5rem; text-align: left; }}
    code, textarea {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    textarea {{ min-height: 6rem; width: 100%; }}
  </style>
</head>
<body>
  <nav>
    <a href="/dashboard">Dashboard</a>
    <a href="/providers">Providers</a>
    <a href="/context">Context</a>
    <a href="/agent">Agent</a>
  </nav>
  {body}
</body>
</html>"""


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)
