from __future__ import annotations

import os
import secrets
import time
from typing import Any

from .crucible_store import CrucibleStore


DEFAULT_PUBLIC_MCP_CREDITS = 5


def starting_credit_runs() -> int:
    raw = os.environ.get("CRUCIBLE_PUBLIC_MCP_STARTING_CREDITS", str(DEFAULT_PUBLIC_MCP_CREDITS))
    try:
        credits = int(raw)
    except ValueError as exc:
        raise ValueError("CRUCIBLE_PUBLIC_MCP_STARTING_CREDITS must be an integer.") from exc
    if credits <= 0:
        raise ValueError("CRUCIBLE_PUBLIC_MCP_STARTING_CREDITS must be positive.")
    return credits


def public_credit_required() -> bool:
    return os.environ.get("CRUCIBLE_PUBLIC_MCP_REQUIRE_CREDITS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def claim_public_mcp_credit(
    store: CrucibleStore,
    *,
    caller_id: str,
    label: str | None = None,
    credit_limit_runs: int | None = None,
) -> dict[str, Any]:
    account = store.ensure_public_mcp_account(
        caller_id,
        label=label,
        credit_limit_runs=credit_limit_runs or starting_credit_runs(),
        now=_now(),
    )
    return _with_policy(account)


def public_mcp_credit_status(store: CrucibleStore, *, caller_id: str) -> dict[str, Any]:
    account = store.get_public_mcp_account(caller_id)
    if account is None:
        account = store.ensure_public_mcp_account(
            caller_id,
            credit_limit_runs=starting_credit_runs(),
            now=_now(),
        )
    return {**_with_policy(account), "usage_events": store.list_public_mcp_usage(caller_id)}


def consume_public_mcp_credit(
    store: CrucibleStore,
    *,
    caller_id: str,
    tool_name: str,
    run_count: int = 1,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = store.consume_public_mcp_credit(
        caller_id,
        tool_name=tool_name,
        run_count=run_count,
        metadata=metadata,
        credit_limit_runs=starting_credit_runs(),
        now=_now(),
        event_id=_new_id("public_mcp_usage"),
    )
    result["account"] = _with_policy(result["account"])
    return result


def _with_policy(account: dict[str, Any]) -> dict[str, Any]:
    return {
        **account,
        "policy": {
            "unit": "run",
            "starting_credit_runs": account["credit_limit_runs"],
            "secret_exposure": "server_only",
        },
    }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"
