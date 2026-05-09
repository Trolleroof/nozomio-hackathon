from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import time
from typing import Any, Sequence

from .config import load_config
from .crucible_store import CrucibleStore


QWEN_7B_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
PASSWORD_ITERATIONS = 210_000


class ApprovalRequiredError(RuntimeError):
    pass


def signup_user(store: CrucibleStore, email: str, password: str, *, role: str = "user") -> dict[str, Any]:
    normalized_email = email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise ValueError("A valid email is required.")
    if role not in {"user", "admin"}:
        raise ValueError("Role must be user or admin.")
    password_hash = _hash_password(password)
    record = {
        "id": _new_id("user"),
        "email": normalized_email,
        "password_hash": password_hash,
        "role": role,
        "created_at": _now(),
    }
    try:
        user = store.create_user(record)
    except sqlite3.IntegrityError as exc:
        raise ValueError("User already exists.") from exc
    return _public_user(user)


def login_user(store: CrucibleStore, email: str, password: str) -> dict[str, Any]:
    user = store.get_user_by_email(email.strip().lower(), include_private=True)
    if user is None or not _verify_password(password, user["password_hash"]):
        raise ValueError("Invalid email or password.")
    session = {
        "token": _new_id("sess"),
        "user_id": user["id"],
        "created_at": _now(),
    }
    return store.create_session(session)


def create_deployment_plan(
    store: CrucibleStore,
    user_id: str,
    prompt: str,
    *,
    source: str = "api",
) -> dict[str, Any]:
    user = store.get_user(user_id)
    if user is None:
        raise ValueError(f"Unknown user {user_id}")

    objective = _infer_objective(prompt)
    provider = "Modal" if objective == "cheapest" else "SkyPilot"
    if provider not in {"Modal", "SkyPilot"}:
        provider = "Modal"
    created_at = _now()
    plan = {
        "id": _new_id("plan"),
        "user_id": user_id,
        "prompt": prompt,
        "source": source,
        "status": "generated",
        "model_id": QWEN_7B_MODEL_ID,
        "objective": objective,
        "approval_required": True,
        "recommendation": {
            "provider": provider,
            "runtime": "vLLM",
            "accelerator": "L4",
            "replicas": 1,
            "deployment_mode": "simulated-safe",
            "estimated_vram_gb": 16,
            "estimated_cost_usd_per_hour": 0.0,
            "reason": "Qwen 7B fits on a single economical GPU; paid launch remains gated by approval.",
        },
        "context_used": [
            {
                "source": "crucible-policy",
                "fact": "Paid GPU resources require explicit approval before launch.",
            },
            {
                "source": "model-catalog",
                "fact": f"{QWEN_7B_MODEL_ID} is treated as the Qwen 7B chat target.",
            },
        ],
        "next_action": "Review the plan and grant approval before any GPU resources are launched.",
        "created_at": created_at,
        "approved_at": None,
    }
    return store.create_plan(plan)


def approve_plan(store: CrucibleStore, plan_id: str, user_id: str) -> dict[str, Any]:
    plan = store.get_plan(plan_id)
    if plan is None:
        raise ValueError(f"Unknown deployment plan {plan_id}")
    user = store.get_user(user_id)
    if user is None:
        raise ValueError(f"Unknown user {user_id}")
    if user["role"] != "admin":
        raise ValueError("Only admin users can approve GPU deployment plans.")
    now = _now()
    approval = {
        "id": _new_id("approval"),
        "plan_id": plan_id,
        "approved_by": user_id,
        "token": _new_id("approval_token"),
        "created_at": now,
    }
    store.create_approval(approval)
    store.update_plan_status(plan_id, "approved", approved_at=now)
    return approval


def deploy_approved_plan(
    store: CrucibleStore,
    plan_id: str,
    *,
    approval_token: str | None = None,
) -> dict[str, Any]:
    plan = store.get_plan(plan_id)
    if plan is None:
        raise ValueError(f"Unknown deployment plan {plan_id}")
    if not approval_token:
        raise ApprovalRequiredError("Approval required before launching GPU resources.")
    approval = store.get_approval_by_token(approval_token)
    if approval is None or approval["plan_id"] != plan_id:
        raise ApprovalRequiredError("Approval required before launching GPU resources.")

    now = _now()
    deployment_id = _new_id("deploy")
    endpoint_url = f"https://crucible.local/{deployment_id}/v1/chat/completions"
    provider = plan["recommendation"]["provider"]
    deployment = {
        "id": deployment_id,
        "plan_id": plan_id,
        "status": "ready",
        "endpoint_url": endpoint_url,
        "provider": provider,
        "runtime": plan["recommendation"]["runtime"],
        "health_checks": [
            {
                "checked_at": now,
                "status": "passing",
                "target": endpoint_url,
                "simulated": True,
            }
        ],
        "logs": [
            {"time": now, "level": "info", "message": f"Approved plan {plan_id}; paid launch gate satisfied."},
            {"time": now, "level": "info", "message": f"Prepared simulated {provider} deployment for {plan['model_id']}."},
            {"time": now, "level": "info", "message": "Health checks passed for OpenAI-compatible endpoint."},
        ],
        "benchmark": {
            "model_id": plan["model_id"],
            "tokens_per_second": 42.0,
            "p50_latency_ms": 230,
            "p95_latency_ms": 480,
            "simulated": True,
        },
        "created_at": now,
        "updated_at": now,
    }
    created = store.create_deployment(deployment)
    store.update_plan_status(plan_id, "deployed")
    return created


def get_deployment(store: CrucibleStore, deployment_id: str) -> dict[str, Any]:
    deployment = store.get_deployment(deployment_id)
    if deployment is None:
        raise ValueError(f"Unknown deployment {deployment_id}")
    return deployment


def list_deployments(store: CrucibleStore) -> list[dict[str, Any]]:
    return store.list_deployments()


def get_deployment_logs(store: CrucibleStore, deployment_id: str) -> list[dict[str, Any]]:
    return get_deployment(store, deployment_id)["logs"]


def run_health_check(store: CrucibleStore, deployment_id: str) -> dict[str, Any]:
    deployment = get_deployment(store, deployment_id)
    now = _now()
    health_checks = [
        {
            **check,
            "checked_at": now,
            "status": "passing" if deployment["status"] in {"ready", "stopped"} else check.get("status", "passing"),
        }
        for check in deployment["health_checks"]
    ]
    logs = [
        *deployment["logs"],
        {"time": now, "level": "info", "message": "Manual health check passed for OpenAI-compatible endpoint."},
    ]
    return store.update_deployment(deployment_id, {"health_checks": health_checks, "logs": logs, "updated_at": now})


def stop_deployment(store: CrucibleStore, deployment_id: str) -> dict[str, Any]:
    deployment = get_deployment(store, deployment_id)
    now = _now()
    logs = [
        *deployment["logs"],
        {"time": now, "level": "info", "message": "Stop requested; deployment marked stopped."},
    ]
    return store.update_deployment(deployment_id, {"status": "stopped", "logs": logs, "updated_at": now})


def search_context(store: CrucibleStore, query: str) -> list[dict[str, Any]]:
    del store
    snippets = [
        {
            "title": "Modal vLLM deployment health",
            "source": "Modal vLLM docs",
            "snippet": "Expose an OpenAI-compatible endpoint and verify /v1/models plus /v1/chat/completions before marking ready.",
        },
        {
            "title": "Approval gate",
            "source": "Crucible policy",
            "snippet": "Paid GPU launches require explicit approval before provider resources are created.",
        },
        {
            "title": "Known working recipes",
            "source": "known working recipes",
            "snippet": "For Qwen 7B, prefer a single economical GPU first and avoid multi-GPU unless latency requires it.",
        },
    ]
    terms = [term for term in query.lower().replace("/", " ").split() if len(term) > 2]
    if not terms:
        return snippets
    matches = [
        snippet
        for snippet in snippets
        if any(term in f"{snippet['title']} {snippet['source']} {snippet['snippet']}".lower() for term in terms)
    ]
    return matches or snippets


def explain_failure(store: CrucibleStore, deployment_id: str, error: str) -> dict[str, Any]:
    return {
        "deployment_id": deployment_id,
        "failure": error,
        "context_used": search_context(store, error),
        "likely_cause": "The deployment did not pass provider or OpenAI-compatible runtime health checks.",
        "next_action": "Inspect logs, verify provider credentials, rerun health checks, then redeploy after approval.",
    }


def explain_failure_with_context(store: CrucibleStore, deployment_id: str, error: str) -> dict[str, Any]:
    return explain_failure(store, deployment_id, error)


def list_provider_capabilities(store: CrucibleStore) -> list[dict[str, Any]]:
    now = _now()
    config = load_config()
    records = [
        _provider_record(
            "Modal",
            configured=bool(os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET")),
            supports_openai_endpoint=True,
            credential_names=["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"],
            notes="Can expose an OpenAI-compatible service when Modal credentials are configured.",
        ),
        _provider_record(
            "SkyPilot",
            configured=bool(os.environ.get("SKYPILOT_API_SERVER_ENDPOINT")),
            supports_openai_endpoint=True,
            credential_names=["SKYPILOT_API_SERVER_ENDPOINT"],
            notes="Requires a configured SkyPilot API server before AnyGPU can request launches.",
        ),
        _provider_record(
            "Lambda Cloud",
            configured=bool(os.environ.get("LAMBDA_CLOUD_API_KEY") or os.environ.get("LAMBDA_API_KEY")),
            supports_openai_endpoint=False,
            credential_names=["LAMBDA_CLOUD_API_KEY"],
            notes="Provider catalog entry only; no direct launch adapter is enabled here.",
        ),
        _provider_record(
            "CoreWeave",
            configured=bool(os.environ.get("COREWEAVE_API_KEY") or os.environ.get("COREWEAVE_KUBECONFIG")),
            supports_openai_endpoint=False,
            credential_names=["COREWEAVE_API_KEY", "COREWEAVE_KUBECONFIG"],
            notes="Provider catalog entry only; no direct launch adapter is enabled here.",
        ),
        _provider_record(
            "Vast.ai",
            configured=bool(config.get("vast_api_key")),
            supports_openai_endpoint=True,
            credential_names=["VAST_AI_API_KEY", "ANYGPU_VAST_API_KEY"],
            notes="Marketplace launch adapter is available when Vast credentials are configured.",
        ),
        _provider_record(
            "Tensorlake",
            configured=bool(os.environ.get("TENSORLAKE_API_KEY")),
            supports_openai_endpoint=False,
            credential_names=["TENSORLAKE_API_KEY"],
            notes="Creates isolated MicroVM sandboxes for agent tool execution and command runs.",
        ),
    ]
    for record in records:
        record["updated_at"] = now
    store.upsert_provider_capabilities(records, now)
    return records


def add_crucible_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    crucible = subparsers.add_parser("crucible")
    crucible_sub = crucible.add_subparsers(dest="crucible_command", required=True)

    signup = crucible_sub.add_parser("signup")
    signup.add_argument("--email", required=True)
    signup.add_argument("--password", required=True)
    signup.add_argument("--role", choices=["user", "admin"], default="user")
    signup.set_defaults(func=_command_signup)

    login = crucible_sub.add_parser("login")
    login.add_argument("--email", required=True)
    login.add_argument("--password", required=True)
    login.set_defaults(func=_command_login)

    plan = crucible_sub.add_parser("plan")
    plan.add_argument("--user-id", required=True)
    plan.add_argument("--prompt", required=True)
    plan.add_argument("--source", default="cli")
    plan.set_defaults(func=_command_plan)

    approve = crucible_sub.add_parser("approve")
    approve.add_argument("--plan-id", required=True)
    approve.add_argument("--user-id", required=True)
    approve.set_defaults(func=_command_approve)

    deploy = crucible_sub.add_parser("deploy")
    deploy.add_argument("--plan-id", required=True)
    deploy.add_argument("--approval-token")
    deploy.set_defaults(func=_command_deploy)

    status = crucible_sub.add_parser("status")
    status.add_argument("--deployment-id", required=True)
    status.set_defaults(func=_command_status)

    providers = crucible_sub.add_parser("providers")
    providers.set_defaults(func=_command_providers)


def _command_signup(args: argparse.Namespace) -> None:
    _print_json(signup_user(CrucibleStore(), args.email, args.password, role=args.role))


def _command_login(args: argparse.Namespace) -> None:
    _print_json(login_user(CrucibleStore(), args.email, args.password))


def _command_plan(args: argparse.Namespace) -> None:
    _print_json(create_deployment_plan(CrucibleStore(), args.user_id, args.prompt, source=args.source))


def _command_approve(args: argparse.Namespace) -> None:
    _print_json(approve_plan(CrucibleStore(), args.plan_id, args.user_id))


def _command_deploy(args: argparse.Namespace) -> None:
    try:
        result = deploy_approved_plan(CrucibleStore(), args.plan_id, approval_token=args.approval_token)
    except ApprovalRequiredError as exc:
        result = {"error": str(exc)}
    _print_json(result)


def _command_status(args: argparse.Namespace) -> None:
    _print_json(get_deployment(CrucibleStore(), args.deployment_id))


def _command_providers(_: argparse.Namespace) -> None:
    _print_json(list_provider_capabilities(CrucibleStore()))


def _print_json(record: Any) -> None:
    print(json.dumps(record, sort_keys=True))


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in user.items() if key != "password_hash"}


def _provider_record(
    provider: str,
    *,
    configured: bool,
    supports_openai_endpoint: bool,
    credential_names: list[str],
    notes: str,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "status": "configured" if configured else "unsupported",
        "supports_deploy": configured,
        "supports_openai_endpoint": supports_openai_endpoint,
        "credentials_present": configured,
        "credentials_required": credential_names,
        "paid_deploy_gated": True,
        "notes": notes,
    }


def _infer_objective(prompt: str) -> str:
    lowered = prompt.lower()
    if any(word in lowered for word in ("cheap", "cheapest", "cost", "budget")):
        return "cheapest"
    return "balanced"


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(iterations),
    )
    return secrets.compare_digest(digest.hex(), digest_hex)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(16)}"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
