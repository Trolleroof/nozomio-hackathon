from __future__ import annotations

import json
import secrets
import sqlite3
import time
from typing import Any

from .crucible_store import CrucibleStore


JSON = dict[str, Any]


class ApprovalRequiredError(RuntimeError):
    """Raised when an agent tries to launch paid compute without an approval row."""


def create_experiment_branch(
    store: CrucibleStore,
    *,
    name: str,
    parent_branch: str = "main",
    schema_snapshot: JSON | None = None,
) -> JSON:
    now = _now()
    record = {
        "name": _required(name, "name"),
        "parent_branch": parent_branch,
        "status": "active",
        "schema_snapshot": schema_snapshot or {},
        "merge_note": None,
        "created_at": now,
        "merged_at": None,
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into rl_experiment_branches (
                name, parent_branch, status, schema_snapshot_json, merge_note, created_at, merged_at
            )
            values (?, ?, ?, ?, ?, ?, ?)
            on conflict(name) do update set
                parent_branch = excluded.parent_branch,
                status = excluded.status,
                schema_snapshot_json = excluded.schema_snapshot_json,
                merge_note = excluded.merge_note,
                merged_at = excluded.merged_at
            """,
            (
                record["name"],
                record["parent_branch"],
                record["status"],
                _dump(record["schema_snapshot"]),
                record["merge_note"],
                record["created_at"],
                record["merged_at"],
            ),
        )
    return get_experiment_branch(store, record["name"])


def get_experiment_branch(store: CrucibleStore, name: str) -> JSON:
    with store._connect() as conn:
        row = conn.execute("select * from rl_experiment_branches where name = ?", (name,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown experiment branch {name}")
    return _branch_from_row(row)


def merge_experiment_branch(store: CrucibleStore, name: str, *, merge_note: str) -> JSON:
    now = _now()
    with store._connect() as conn:
        conn.execute(
            """
            update rl_experiment_branches
            set status = 'merged', merge_note = ?, merged_at = ?
            where name = ?
            """,
            (merge_note, now, name),
        )
    return get_experiment_branch(store, name)


def create_environment_contract(
    store: CrucibleStore,
    *,
    name: str,
    env_spec: JSON,
    observation_schema: JSON,
    action_schema: JSON,
    reward_spec: JSON,
    pass_criteria: JSON,
    branch_name: str = "main",
    version: int | None = None,
) -> JSON:
    _ensure_branch(store, branch_name)
    next_version = version or _next_contract_version(store, name, branch_name)
    now = _now()
    record = {
        "id": _new_id("env_contract"),
        "name": _required(name, "name"),
        "version": next_version,
        "branch_name": branch_name,
        "env_spec": env_spec,
        "observation_schema": observation_schema,
        "action_schema": action_schema,
        "reward_spec": reward_spec,
        "pass_criteria": pass_criteria,
        "created_at": now,
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into rl_environment_contracts (
                id, name, version, branch_name, env_spec_json, observation_schema_json,
                action_schema_json, reward_spec_json, pass_criteria_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["name"],
                record["version"],
                record["branch_name"],
                _dump(record["env_spec"]),
                _dump(record["observation_schema"]),
                _dump(record["action_schema"]),
                _dump(record["reward_spec"]),
                _dump(record["pass_criteria"]),
                record["created_at"],
            ),
        )
    return get_environment_contract(store, record["id"])


def get_environment_contract(store: CrucibleStore, contract_id: str) -> JSON:
    with store._connect() as conn:
        row = conn.execute("select * from rl_environment_contracts where id = ?", (contract_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown environment contract {contract_id}")
    return _contract_from_row(row)


def request_gpu_run(
    store: CrucibleStore,
    *,
    user_id: str,
    prompt: str,
    env_contract_id: str,
    provider_offers: list[JSON],
    cost_estimate: JSON,
    source_agent: str = "agent",
) -> JSON:
    user = store.get_user(user_id)
    if user is None:
        raise ValueError(f"Unknown user {user_id}")
    contract = get_environment_contract(store, env_contract_id)
    now = _now()
    sorted_offers = sorted(
        provider_offers,
        key=lambda offer: (
            not bool(offer.get("available", True)),
            float(offer.get("price_per_hr") or offer.get("price_per_hour_usd") or 1_000_000),
            str(offer.get("provider") or ""),
        ),
    )
    record = {
        "id": _new_id("run_capsule"),
        "user_id": user_id,
        "env_contract_id": env_contract_id,
        "branch_name": contract["branch_name"],
        "prompt": _required(prompt, "prompt"),
        "source_agent": source_agent,
        "status": "approval_required",
        "provider": None,
        "provider_offers": sorted_offers,
        "cost_estimate": cost_estimate,
        "approval_token": None,
        "logs": [
            {
                "time": now,
                "level": "info",
                "message": "Run capsule created; signed approval required before paid GPU launch.",
            }
        ],
        "metrics": {},
        "audit": {"passed": False, "reason": "not_run"},
        "model_artifact_uri": None,
        "created_at": now,
        "updated_at": now,
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into rl_run_capsules (
                id, user_id, env_contract_id, branch_name, prompt, source_agent, status,
                provider, provider_offers_json, cost_estimate_json, approval_token,
                logs_json, metrics_json, audit_json, model_artifact_uri, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _capsule_values(record),
        )
    return get_run_capsule(store, record["id"])


def get_run_capsule(store: CrucibleStore, run_id: str) -> JSON:
    with store._connect() as conn:
        row = conn.execute("select * from rl_run_capsules where id = ?", (run_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown run capsule {run_id}")
    return _capsule_from_row(row)


def list_run_capsules(store: CrucibleStore) -> list[JSON]:
    with store._connect() as conn:
        rows = conn.execute("select * from rl_run_capsules order by created_at desc, id desc").fetchall()
    return [_capsule_from_row(row) for row in rows]


def approve_gpu_run(
    store: CrucibleStore,
    *,
    run_id: str,
    approved_by: str,
    provider: str,
    budget_usd: float,
    max_runtime_minutes: int,
    teardown_policy: JSON,
) -> JSON:
    capsule = get_run_capsule(store, run_id)
    user = store.get_user(approved_by)
    if user is None:
        raise ValueError(f"Unknown user {approved_by}")
    if user["role"] != "admin":
        raise ValueError("Only admin users can approve paid GPU runs.")
    if budget_usd <= 0:
        raise ValueError("budget_usd must be positive.")
    if max_runtime_minutes <= 0:
        raise ValueError("max_runtime_minutes must be positive.")

    now = _now()
    approval = {
        "id": _new_id("gpu_approval"),
        "run_id": capsule["id"],
        "approved_by": approved_by,
        "provider": _required(provider, "provider"),
        "budget_usd": float(budget_usd),
        "max_runtime_minutes": int(max_runtime_minutes),
        "teardown_policy": teardown_policy,
        "token": _new_id("approval_token"),
        "status": "signed",
        "signed_at": now,
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into rl_compute_approvals (
                id, run_id, approved_by, provider, budget_usd, max_runtime_minutes,
                teardown_policy_json, token, status, signed_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval["id"],
                approval["run_id"],
                approval["approved_by"],
                approval["provider"],
                approval["budget_usd"],
                approval["max_runtime_minutes"],
                _dump(approval["teardown_policy"]),
                approval["token"],
                approval["status"],
                approval["signed_at"],
            ),
        )
    return get_gpu_approval_by_token(store, approval["token"])


def get_gpu_approval_by_token(store: CrucibleStore, token: str) -> JSON | None:
    with store._connect() as conn:
        row = conn.execute("select * from rl_compute_approvals where token = ?", (token,)).fetchone()
    return _approval_from_row(row) if row else None


def launch_gpu_run(store: CrucibleStore, run_id: str, *, approval_token: str | None = None) -> JSON:
    capsule = get_run_capsule(store, run_id)
    approval = get_gpu_approval_by_token(store, approval_token or "")
    if approval is None or approval["run_id"] != run_id or approval["status"] != "signed":
        raise ApprovalRequiredError("A signed approval row is required before launching paid GPU resources.")

    now = _now()
    logs = [
        *capsule["logs"],
        {
            "time": now,
            "level": "info",
            "message": f"Signed approval accepted for provider {approval['provider']}; run marked running.",
        },
    ]
    updates = {
        "status": "running",
        "provider": approval["provider"],
        "approval_token": approval["token"],
        "logs": logs,
        "updated_at": now,
    }
    _update_capsule(store, run_id, updates)
    return get_run_capsule(store, run_id)


def record_training_event(
    store: CrucibleStore,
    *,
    run_id: str,
    phase: str,
    rollout_count: int | None = None,
    reward_mean: float | None = None,
    success_rate: float | None = None,
    cost_burn_usd: float | None = None,
    gpu_name: str | None = None,
    message: str = "",
) -> JSON:
    capsule = get_run_capsule(store, run_id)
    now = _now()
    record = {
        "id": _new_id("train_evt"),
        "run_id": run_id,
        "channel": f"training:{run_id}",
        "phase": _required(phase, "phase"),
        "rollout_count": rollout_count,
        "reward_mean": reward_mean,
        "success_rate": success_rate,
        "cost_burn_usd": cost_burn_usd,
        "gpu_name": gpu_name,
        "message": message,
        "created_at": now,
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into rl_training_events (
                id, run_id, channel, phase, rollout_count, reward_mean, success_rate,
                cost_burn_usd, gpu_name, message, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["run_id"],
                record["channel"],
                record["phase"],
                record["rollout_count"],
                record["reward_mean"],
                record["success_rate"],
                record["cost_burn_usd"],
                record["gpu_name"],
                record["message"],
                record["created_at"],
            ),
        )
    metrics = {
        **capsule["metrics"],
        "latest_phase": phase,
        "rollout_count": rollout_count,
        "reward_mean": reward_mean,
        "success_rate": success_rate,
        "cost_burn_usd": cost_burn_usd,
        "gpu_name": gpu_name,
    }
    logs = [*capsule["logs"], {"time": now, "level": "info", "message": message or f"Training phase {phase} recorded."}]
    _update_capsule(store, run_id, {"metrics": metrics, "logs": logs, "updated_at": now})
    return record


def record_compute_memory(
    store: CrucibleStore,
    *,
    run_id: str | None,
    provider: str,
    gpu_name: str | None,
    event_type: str,
    status: str,
    summary: str,
    pricing: JSON | None = None,
    compatibility: JSON | None = None,
    region: str | None = None,
) -> JSON:
    if run_id:
        get_run_capsule(store, run_id)
    now = _now()
    record = {
        "id": _new_id("compute_mem"),
        "run_id": run_id,
        "provider": _required(provider, "provider"),
        "gpu_name": gpu_name,
        "region": region,
        "event_type": _required(event_type, "event_type"),
        "status": _required(status, "status"),
        "summary": _required(summary, "summary"),
        "pricing": pricing or {},
        "compatibility": compatibility or {},
        "created_at": now,
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into rl_compute_memory (
                id, run_id, provider, gpu_name, region, event_type, status, summary,
                pricing_json, compatibility_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["run_id"],
                record["provider"],
                record["gpu_name"],
                record["region"],
                record["event_type"],
                record["status"],
                record["summary"],
                _dump(record["pricing"]),
                _dump(record["compatibility"]),
                record["created_at"],
            ),
        )
    return record


def publish_run_artifact(
    store: CrucibleStore,
    *,
    run_id: str,
    kind: str,
    uri: str,
    metadata: JSON,
    storage_bucket: str | None = "rl-runs",
) -> JSON:
    capsule = get_run_capsule(store, run_id)
    now = _now()
    record = {
        "id": _new_id("artifact"),
        "run_id": run_id,
        "kind": _required(kind, "kind"),
        "uri": _required(uri, "uri"),
        "storage_bucket": storage_bucket,
        "metadata": metadata,
        "passed": bool(metadata.get("passed", False)),
        "gpu_name": metadata.get("gpu_name"),
        "cost_usd": metadata.get("cost_usd"),
        "reward_delta": metadata.get("reward_delta"),
        "success_rate_delta": metadata.get("success_rate_delta"),
        "created_at": now,
    }
    with store._connect() as conn:
        conn.execute(
            """
            insert into rl_run_artifacts (
                id, run_id, kind, uri, storage_bucket, metadata_json, passed,
                gpu_name, cost_usd, reward_delta, success_rate_delta, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["run_id"],
                record["kind"],
                record["uri"],
                record["storage_bucket"],
                _dump(record["metadata"]),
                1 if record["passed"] else 0,
                record["gpu_name"],
                record["cost_usd"],
                record["reward_delta"],
                record["success_rate_delta"],
                record["created_at"],
            ),
        )
    audit = {
        **capsule["audit"],
        "passed": record["passed"],
        "gpu_name": record["gpu_name"],
        "cost_usd": record["cost_usd"],
        "reward_delta": record["reward_delta"],
        "success_rate_delta": record["success_rate_delta"],
        "artifact_uri": record["uri"],
    }
    updates: JSON = {"audit": audit, "status": "passed" if record["passed"] else "failed", "updated_at": now}
    if record["kind"] in {"model", "checkpoint", "model_checkpoint"}:
        updates["model_artifact_uri"] = record["uri"]
    _update_capsule(store, run_id, updates)
    return record


def recommend_next_gpu_run(
    store: CrucibleStore,
    *,
    env_contract_id: str | None = None,
    objective: str = "cheapest_verified_improving",
) -> JSON:
    where = "where a.passed = 1"
    params: list[Any] = []
    if env_contract_id:
        where += " and c.env_contract_id = ?"
        params.append(env_contract_id)
    with store._connect() as conn:
        rows = conn.execute(
            f"""
            select
                c.id as run_id,
                c.provider as provider,
                c.prompt as prompt,
                c.env_contract_id as env_contract_id,
                a.gpu_name as gpu_name,
                a.cost_usd as cost_usd,
                a.reward_delta as reward_delta,
                a.success_rate_delta as success_rate_delta,
                a.uri as artifact_uri,
                a.created_at as created_at
            from rl_run_artifacts a
            join rl_run_capsules c on c.id = a.run_id
            {where}
            order by coalesce(a.cost_usd, 999999.0) asc, coalesce(a.success_rate_delta, 0) desc, a.created_at desc
            limit 5
            """,
            params,
        ).fetchall()
    evidence = [dict(row) for row in rows]
    if not evidence:
        return {
            "objective": objective,
            "recommended_provider": None,
            "reason": "No passing GPU/RL artifacts have been published for this scope yet.",
            "evidence": [],
        }
    best = evidence[0]
    return {
        "objective": objective,
        "recommended_provider": best["provider"],
        "recommended_gpu_name": best["gpu_name"],
        "recommended_env_contract_id": best["env_contract_id"],
        "reason": "Selected the lowest-cost passing artifact with improvement metadata.",
        "evidence": evidence,
    }


def _update_capsule(store: CrucibleStore, run_id: str, updates: JSON) -> None:
    current = get_run_capsule(store, run_id)
    merged = {**current, **updates}
    with store._connect() as conn:
        conn.execute(
            """
            update rl_run_capsules
            set status = ?, provider = ?, approval_token = ?, logs_json = ?, metrics_json = ?,
                audit_json = ?, model_artifact_uri = ?, updated_at = ?
            where id = ?
            """,
            (
                merged["status"],
                merged.get("provider"),
                merged.get("approval_token"),
                _dump(merged["logs"]),
                _dump(merged["metrics"]),
                _dump(merged["audit"]),
                merged.get("model_artifact_uri"),
                merged["updated_at"],
                run_id,
            ),
        )


def _ensure_branch(store: CrucibleStore, name: str) -> None:
    with store._connect() as conn:
        row = conn.execute("select name from rl_experiment_branches where name = ?", (name,)).fetchone()
        if row is None:
            now = _now()
            conn.execute(
                """
                insert into rl_experiment_branches (
                    name, parent_branch, status, schema_snapshot_json, merge_note, created_at, merged_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, None, "active", _dump({}), None, now, None),
            )


def _next_contract_version(store: CrucibleStore, name: str, branch_name: str) -> int:
    with store._connect() as conn:
        row = conn.execute(
            "select max(version) as version from rl_environment_contracts where name = ? and branch_name = ?",
            (name, branch_name),
        ).fetchone()
    return int(row["version"] or 0) + 1


def _required(value: str, name: str) -> str:
    if not value:
        raise ValueError(f"{name} is required.")
    return value


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(16)}"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _load(value: str) -> Any:
    return json.loads(value)


def _branch_from_row(row: sqlite3.Row) -> JSON:
    record = dict(row)
    record["schema_snapshot"] = _load(record.pop("schema_snapshot_json"))
    return record


def _contract_from_row(row: sqlite3.Row) -> JSON:
    record = dict(row)
    record["env_spec"] = _load(record.pop("env_spec_json"))
    record["observation_schema"] = _load(record.pop("observation_schema_json"))
    record["action_schema"] = _load(record.pop("action_schema_json"))
    record["reward_spec"] = _load(record.pop("reward_spec_json"))
    record["pass_criteria"] = _load(record.pop("pass_criteria_json"))
    return record


def _capsule_from_row(row: sqlite3.Row) -> JSON:
    record = dict(row)
    record["provider_offers"] = _load(record.pop("provider_offers_json"))
    record["cost_estimate"] = _load(record.pop("cost_estimate_json"))
    record["logs"] = _load(record.pop("logs_json"))
    record["metrics"] = _load(record.pop("metrics_json"))
    record["audit"] = _load(record.pop("audit_json"))
    return record


def _approval_from_row(row: sqlite3.Row) -> JSON:
    record = dict(row)
    record["teardown_policy"] = _load(record.pop("teardown_policy_json"))
    return record


def _capsule_values(record: JSON) -> tuple[Any, ...]:
    return (
        record["id"],
        record["user_id"],
        record["env_contract_id"],
        record["branch_name"],
        record["prompt"],
        record["source_agent"],
        record["status"],
        record["provider"],
        _dump(record["provider_offers"]),
        _dump(record["cost_estimate"]),
        record["approval_token"],
        _dump(record["logs"]),
        _dump(record["metrics"]),
        _dump(record["audit"]),
        record["model_artifact_uri"],
        record["created_at"],
        record["updated_at"],
    )
