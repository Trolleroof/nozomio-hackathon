from __future__ import annotations

import json
import sys
from typing import Any

from .crucible import create_deployment_plan, ensure_backend_user
from .crucible_mcp import handle_tool_call
from .crucible_store import CrucibleStore


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            raise ValueError("Bridge payload must be a JSON object.")
        action = payload.get("action") or "plan"
        store = CrucibleStore()
        if action == "mcp_snapshot":
            print(json.dumps(_mcp_snapshot(store), sort_keys=True))
            return 0
        if action == "mcp_call":
            tool_name = _required_string(payload, "toolName")
            arguments = payload.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise ValueError("arguments must be a JSON object.")
            print(json.dumps(handle_tool_call(store, tool_name, arguments), sort_keys=True))
            return 0
        if action != "plan":
            raise ValueError(f"Unsupported bridge action {action}.")
        user = ensure_backend_user(
            store,
            str(payload.get("userId") or "anonymous-web-user"),
            email=_optional_string(payload.get("email")),
        )
        plan = create_deployment_plan(
            store,
            user["id"],
            _required_string(payload, "prompt"),
            source=_optional_string(payload.get("sourceAgent")) or "web",
            model_id=_optional_string(payload.get("modelId")),
            objective=_optional_string(payload.get("objective")),
        )
        print(json.dumps(plan, sort_keys=True))
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


def _mcp_snapshot(store: CrucibleStore) -> dict[str, Any]:
    deployments = handle_tool_call(store, "crucible_list_deployments", {})
    run_capsules = handle_tool_call(store, "crucible_list_run_capsules", {})
    return {
        "source": "crucible_mcp",
        "deployments": [] if deployments.get("isError") else deployments.get("content", []),
        "run_capsules": [] if run_capsules.get("isError") else run_capsules.get("content", []),
        "errors": [
            response["content"]["error"]
            for response in (deployments, run_capsules)
            if response.get("isError") and isinstance(response.get("content"), dict) and response["content"].get("error")
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
