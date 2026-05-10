from __future__ import annotations

import json
import sys
from typing import Any

from .crucible import approve_plan, create_deployment_plan, deploy_approved_plan, ensure_backend_user
from .crucible_store import CrucibleStore


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise ValueError("Bridge payload must be a JSON object.")
        store = CrucibleStore()
        action = payload.get("action") or "plan"
        if action == "plan":
            result = _create_plan(store, payload)
        elif action == "deploy":
            result = _deploy_plan(store, payload)
        else:
            raise ValueError(f"Unsupported bridge action {action}.")
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = _optional_string(payload.get(key))
    if not value:
        raise ValueError(f"{key} is required.")
    return value


def _optional_string(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _create_plan(store: CrucibleStore, payload: dict[str, Any]) -> dict[str, Any]:
    user = ensure_backend_user(
        store,
        str(payload.get("userId") or "anonymous-web-user"),
        email=_optional_string(payload.get("email")),
    )
    return create_deployment_plan(
        store,
        user["id"],
        _required_string(payload, "prompt"),
        source=_optional_string(payload.get("sourceAgent")) or "web",
        model_id=_optional_string(payload.get("modelId")),
        objective=_optional_string(payload.get("objective")),
    )


def _deploy_plan(store: CrucibleStore, payload: dict[str, Any]) -> dict[str, Any]:
    plan_id = _required_string(payload, "planId")
    approver = ensure_backend_user(
        store,
        str(payload.get("approverId") or "web-deployment-approver"),
        email=_optional_string(payload.get("approverEmail")) or "web-deployment-approver@web.crucible.local",
        role="admin",
    )
    approval = approve_plan(store, plan_id, approver["id"])
    deployment = deploy_approved_plan(store, plan_id, approval_token=approval["token"])
    deployment["approval"] = approval
    return deployment


if __name__ == "__main__":
    raise SystemExit(main())
