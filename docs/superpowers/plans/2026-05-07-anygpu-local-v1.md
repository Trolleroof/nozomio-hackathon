# AnyGPU Local V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully functional local v1 of the AnyGPU lifecycle: connect/verify compute, register/profile/benchmark models, create policies, deploy endpoints, operate status/logs/metrics/costs, optimize routes, and serve an OpenAI-compatible local gateway.

**Architecture:** The CLI is a stdlib Python package backed by a JSON control-plane state file under `ANYGPU_HOME`. Domain services normalize managed/BYOC compute into certified pools, produce deterministic profile/benchmark results, select deployment routes from policy constraints, and record usage/events. A stdlib HTTP gateway exposes `/healthz`, `/v1/chat/completions`, and `/v1/completions` against already deployed routes.

**Tech Stack:** Python 3.11+ stdlib, `argparse`, `json`, `http.server`, `unittest`/`pytest` compatible tests.

---

### Task 1: End-to-End CLI Flow

**Files:**
- Create: `tests/test_cli_flow.py`
- Create: `anygpu/__init__.py`
- Create: `anygpu/__main__.py`
- Create: `anygpu/state.py`
- Create: `anygpu/domain.py`
- Create: `anygpu/cli.py`

- [x] **Step 1: Write the failing test**

The test runs real CLI subprocesses with an isolated `ANYGPU_HOME` and checks the production lifecycle from org creation through deployment status.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_flow.py -q`
Expected: FAIL because `anygpu.cli` does not exist yet.

- [x] **Step 3: Write minimal implementation**

Implement JSON state, lifecycle operations, deterministic profiling/benchmarking, route selection, and CLI rendering.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_flow.py -q`
Expected: PASS.

### Task 2: OpenAI-Compatible Gateway

**Files:**
- Create: `tests/test_gateway.py`
- Create: `anygpu/gateway.py`
- Modify: `anygpu/cli.py`
- Modify: `anygpu/domain.py`

- [x] **Step 1: Write the failing test**

The test creates a deployment in isolated state and calls the gateway app directly through a local HTTP server.

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gateway.py -q`
Expected: FAIL because `anygpu.gateway` does not exist yet.

- [x] **Step 3: Write minimal implementation**

Implement health and OpenAI-compatible completions, including route health checks, deterministic response text, token usage, events, and costs.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gateway.py -q`
Expected: PASS.

### Task 3: Packaging And Smoke Verification

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`

- [x] **Step 1: Add package metadata and usage docs**

Expose the console script as `anygpu = anygpu.cli:main` and document the local production flow.

- [x] **Step 2: Run full tests**

Run: `python -m pytest -q`
Expected: PASS.

- [x] **Step 3: Run CLI smoke commands**

Run representative `python -m anygpu ...` commands against `.local-anygpu`.
Expected: commands create org/project/compute/model/policy/deployment and show a live endpoint.

- [x] **Step 4: Start gateway**

Run: `python -m anygpu gateway --host 127.0.0.1 --port 8765`
Expected: local gateway accepts OpenAI-compatible requests.
