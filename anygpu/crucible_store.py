from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .state import state_dir


class CrucibleStore:
    """Small SQLite persistence layer for Crucible records."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else state_dir() / "crucible.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists users (
                    id text primary key,
                    email text not null unique,
                    password_hash text not null,
                    role text not null,
                    created_at text not null
                );

                create table if not exists sessions (
                    token text primary key,
                    user_id text not null references users(id),
                    created_at text not null
                );

                create table if not exists deployment_plans (
                    id text primary key,
                    user_id text not null references users(id),
                    prompt text not null,
                    source text not null,
                    status text not null,
                    model_id text not null,
                    objective text not null,
                    approval_required integer not null,
                    recommendation_json text not null,
                    context_used_json text not null,
                    next_action text not null,
                    created_at text not null,
                    approved_at text
                );

                create table if not exists approvals (
                    id text primary key,
                    plan_id text not null references deployment_plans(id),
                    approved_by text not null references users(id),
                    token text not null unique,
                    created_at text not null
                );

                create table if not exists deployments (
                    id text primary key,
                    plan_id text not null references deployment_plans(id),
                    status text not null,
                    endpoint_url text not null,
                    provider text not null,
                    runtime text not null,
                    health_checks_json text not null,
                    logs_json text not null,
                    benchmark_json text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists provider_capabilities (
                    provider text primary key,
                    record_json text not null,
                    updated_at text not null
                );

                create table if not exists rl_experiment_branches (
                    name text primary key,
                    parent_branch text,
                    status text not null,
                    schema_snapshot_json text not null,
                    merge_note text,
                    created_at text not null,
                    merged_at text
                );

                create table if not exists rl_environment_contracts (
                    id text primary key,
                    name text not null,
                    version integer not null,
                    branch_name text not null,
                    env_spec_json text not null,
                    observation_schema_json text not null,
                    action_schema_json text not null,
                    reward_spec_json text not null,
                    pass_criteria_json text not null,
                    created_at text not null
                );

                create table if not exists rl_run_capsules (
                    id text primary key,
                    user_id text not null references users(id),
                    env_contract_id text not null references rl_environment_contracts(id),
                    branch_name text not null,
                    prompt text not null,
                    source_agent text not null,
                    status text not null,
                    provider text,
                    provider_offers_json text not null,
                    cost_estimate_json text not null,
                    approval_token text,
                    logs_json text not null,
                    metrics_json text not null,
                    audit_json text not null,
                    model_artifact_uri text,
                    created_at text not null,
                    updated_at text not null
                );

                create table if not exists rl_compute_approvals (
                    id text primary key,
                    run_id text not null references rl_run_capsules(id),
                    approved_by text not null references users(id),
                    provider text not null,
                    budget_usd real not null,
                    max_runtime_minutes integer not null,
                    teardown_policy_json text not null,
                    token text not null unique,
                    status text not null,
                    signed_at text not null
                );

                create table if not exists rl_compute_memory (
                    id text primary key,
                    run_id text references rl_run_capsules(id),
                    provider text not null,
                    gpu_name text,
                    region text,
                    event_type text not null,
                    status text not null,
                    summary text not null,
                    pricing_json text not null,
                    compatibility_json text not null,
                    created_at text not null
                );

                create table if not exists rl_training_events (
                    id text primary key,
                    run_id text not null references rl_run_capsules(id),
                    channel text not null,
                    phase text not null,
                    rollout_count integer,
                    reward_mean real,
                    success_rate real,
                    cost_burn_usd real,
                    gpu_name text,
                    message text not null,
                    created_at text not null
                );

                create table if not exists rl_run_artifacts (
                    id text primary key,
                    run_id text not null references rl_run_capsules(id),
                    kind text not null,
                    uri text not null,
                    storage_bucket text,
                    metadata_json text not null,
                    passed integer not null,
                    gpu_name text,
                    cost_usd real,
                    reward_delta real,
                    success_rate_delta real,
                    created_at text not null
                );
                """
            )

    def create_user(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                insert into users (id, email, password_hash, role, created_at)
                values (:id, :email, :password_hash, :role, :created_at)
                """,
                record,
            )
        return self.get_user(record["id"], include_private=True)

    def get_user(self, user_id: str, *, include_private: bool = False) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from users where id = ?", (user_id,)).fetchone()
        return self._user_from_row(row, include_private=include_private)

    def get_user_by_email(self, email: str, *, include_private: bool = False) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from users where email = ?", (email,)).fetchone()
        return self._user_from_row(row, include_private=include_private)

    def create_session(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                "insert into sessions (token, user_id, created_at) values (:token, :user_id, :created_at)",
                record,
            )
        return dict(record)

    def create_plan(self, record: dict[str, Any]) -> dict[str, Any]:
        encoded = dict(record)
        encoded["approval_required"] = 1 if record["approval_required"] else 0
        encoded["recommendation_json"] = json.dumps(record["recommendation"], sort_keys=True)
        encoded["context_used_json"] = json.dumps(record["context_used"], sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                insert into deployment_plans (
                    id, user_id, prompt, source, status, model_id, objective,
                    approval_required, recommendation_json, context_used_json,
                    next_action, created_at, approved_at
                )
                values (
                    :id, :user_id, :prompt, :source, :status, :model_id, :objective,
                    :approval_required, :recommendation_json, :context_used_json,
                    :next_action, :created_at, :approved_at
                )
                """,
                encoded,
            )
        created = self.get_plan(record["id"])
        if created is None:
            raise RuntimeError("Failed to persist deployment plan")
        return created

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from deployment_plans where id = ?", (plan_id,)).fetchone()
        if row is None:
            return None
        return self._plan_from_row(row)

    def update_plan_status(self, plan_id: str, status: str, *, approved_at: str | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                "update deployment_plans set status = ?, approved_at = coalesce(?, approved_at) where id = ?",
                (status, approved_at, plan_id),
            )
        updated = self.get_plan(plan_id)
        if updated is None:
            raise ValueError(f"Unknown deployment plan {plan_id}")
        return updated

    def create_approval(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                """
                insert into approvals (id, plan_id, approved_by, token, created_at)
                values (:id, :plan_id, :approved_by, :token, :created_at)
                """,
                record,
            )
        return dict(record)

    def get_approval_by_token(self, token: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from approvals where token = ?", (token,)).fetchone()
        return dict(row) if row else None

    def create_deployment(self, record: dict[str, Any]) -> dict[str, Any]:
        encoded = dict(record)
        encoded["health_checks_json"] = json.dumps(record["health_checks"], sort_keys=True)
        encoded["logs_json"] = json.dumps(record["logs"], sort_keys=True)
        encoded["benchmark_json"] = json.dumps(record["benchmark"], sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                insert into deployments (
                    id, plan_id, status, endpoint_url, provider, runtime,
                    health_checks_json, logs_json, benchmark_json, created_at, updated_at
                )
                values (
                    :id, :plan_id, :status, :endpoint_url, :provider, :runtime,
                    :health_checks_json, :logs_json, :benchmark_json, :created_at, :updated_at
                )
                """,
                encoded,
            )
        created = self.get_deployment(record["id"])
        if created is None:
            raise RuntimeError("Failed to persist deployment")
        return created

    def get_deployment(self, deployment_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("select * from deployments where id = ?", (deployment_id,)).fetchone()
        if row is None:
            return None
        return self._deployment_from_row(row)

    def list_deployments(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select * from deployments order by created_at desc, id desc").fetchall()
        return [self._deployment_from_row(row) for row in rows]

    def update_deployment(self, deployment_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        current = self.get_deployment(deployment_id)
        if current is None:
            raise ValueError(f"Unknown deployment {deployment_id}")
        merged = {**current, **updates}
        encoded = {
            "id": deployment_id,
            "status": merged["status"],
            "endpoint_url": merged["endpoint_url"],
            "provider": merged["provider"],
            "runtime": merged["runtime"],
            "health_checks_json": json.dumps(merged["health_checks"], sort_keys=True),
            "logs_json": json.dumps(merged["logs"], sort_keys=True),
            "benchmark_json": json.dumps(merged["benchmark"], sort_keys=True),
            "updated_at": merged["updated_at"],
        }
        with self._connect() as conn:
            conn.execute(
                """
                update deployments
                set status = :status,
                    endpoint_url = :endpoint_url,
                    provider = :provider,
                    runtime = :runtime,
                    health_checks_json = :health_checks_json,
                    logs_json = :logs_json,
                    benchmark_json = :benchmark_json,
                    updated_at = :updated_at
                where id = :id
                """,
                encoded,
            )
        updated = self.get_deployment(deployment_id)
        if updated is None:
            raise RuntimeError("Failed to update deployment")
        return updated

    def upsert_provider_capabilities(self, records: list[dict[str, Any]], updated_at: str) -> None:
        with self._connect() as conn:
            for record in records:
                conn.execute(
                    """
                    insert into provider_capabilities (provider, record_json, updated_at)
                    values (?, ?, ?)
                    on conflict(provider) do update set
                        record_json = excluded.record_json,
                        updated_at = excluded.updated_at
                    """,
                    (record["provider"], json.dumps(record, sort_keys=True), updated_at),
                )

    def list_provider_capabilities(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("select record_json from provider_capabilities order by provider").fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    @staticmethod
    def _user_from_row(row: sqlite3.Row | None, *, include_private: bool) -> dict[str, Any] | None:
        if row is None:
            return None
        user = dict(row)
        if not include_private:
            user.pop("password_hash", None)
        return user

    @staticmethod
    def _plan_from_row(row: sqlite3.Row) -> dict[str, Any]:
        plan = dict(row)
        plan["approval_required"] = bool(plan["approval_required"])
        plan["recommendation"] = json.loads(plan.pop("recommendation_json"))
        plan["context_used"] = json.loads(plan.pop("context_used_json"))
        return plan

    @staticmethod
    def _deployment_from_row(row: sqlite3.Row) -> dict[str, Any]:
        deployment = dict(row)
        deployment["health_checks"] = json.loads(deployment.pop("health_checks_json"))
        deployment["logs"] = json.loads(deployment.pop("logs_json"))
        deployment["benchmark"] = json.loads(deployment.pop("benchmark_json"))
        return deployment
