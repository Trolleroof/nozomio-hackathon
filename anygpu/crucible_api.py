from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .crucible import (
    ApprovalRequiredError,
    approve_plan,
    create_deployment_plan,
    deploy_approved_plan,
    ensure_backend_user,
    get_deployment,
    get_deployment_logs,
    list_deployments,
    run_health_check,
    stop_deployment,
)
from .crucible_store import CrucibleStore


class DeploymentPlanRequest(BaseModel):
    user_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    email: str | None = None
    role: Literal["user", "admin"] = "user"
    source_agent: str | None = None
    model_id: str | None = None
    objective: str | None = None


class ApproveDeploymentPlanRequest(BaseModel):
    user_id: str = Field(min_length=1)
    email: str | None = None


class DeployRequest(BaseModel):
    plan_id: str = Field(min_length=1)
    approval_token: str | None = None


def create_app(store: CrucibleStore | None = None) -> FastAPI:
    app = FastAPI(title="Crucible Deployment API", version="0.1.0")

    def active_store() -> CrucibleStore:
        return store or CrucibleStore()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/deployment-plans", status_code=201)
    def create_plan(request: DeploymentPlanRequest) -> dict[str, Any]:
        try:
            db = active_store()
            user = ensure_backend_user(db, request.user_id, email=request.email, role=request.role)
            return create_deployment_plan(
                db,
                user["id"],
                request.prompt,
                source=request.source_agent or "api",
                model_id=request.model_id,
                objective=request.objective,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/deployment-plans/{plan_id}/approve")
    def approve_deployment_plan(plan_id: str, request: ApproveDeploymentPlanRequest) -> dict[str, Any]:
        try:
            db = active_store()
            ensure_backend_user(db, request.user_id, email=request.email, role="admin")
            return approve_plan(db, plan_id, request.user_id)
        except ValueError as exc:
            raise _http_error(exc) from exc

    @app.post("/deployments", status_code=201)
    def deploy(request: DeployRequest) -> dict[str, Any]:
        try:
            return deploy_approved_plan(
                active_store(),
                request.plan_id,
                approval_token=request.approval_token,
            )
        except ApprovalRequiredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise _http_error(exc) from exc

    @app.get("/deployments")
    def list_deployment_records() -> dict[str, Any]:
        deployments = list_deployments(active_store())
        return {"deployments": deployments, "count": len(deployments)}

    @app.get("/deployments/{deployment_id}")
    def get_deployment_record(deployment_id: str) -> dict[str, Any]:
        try:
            return get_deployment(active_store(), deployment_id)
        except ValueError as exc:
            raise _http_error(exc) from exc

    @app.get("/deployments/{deployment_id}/logs")
    def get_deployment_log_records(deployment_id: str) -> dict[str, Any]:
        try:
            logs = get_deployment_logs(active_store(), deployment_id)
            return {"deployment_id": deployment_id, "logs": logs}
        except ValueError as exc:
            raise _http_error(exc) from exc

    @app.post("/deployments/{deployment_id}/health")
    def run_deployment_health_check(deployment_id: str) -> dict[str, Any]:
        try:
            return run_health_check(active_store(), deployment_id)
        except ValueError as exc:
            raise _http_error(exc) from exc

    @app.post("/deployments/{deployment_id}/stop")
    def stop_deployment_record(deployment_id: str) -> dict[str, Any]:
        try:
            return stop_deployment(active_store(), deployment_id)
        except ValueError as exc:
            raise _http_error(exc) from exc

    return app


def _http_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 404 if message.startswith("Unknown ") else 400
    return HTTPException(status_code=status_code, detail=message)


app = create_app()
