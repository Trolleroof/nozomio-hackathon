# Local llama.cpp Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one partially real execution path to AnyGPU: local llama.cpp serving for GGUF models, while preserving simulated managed/BYOC behavior.

**Architecture:** Add a small adapter layer: config loading, a LocalProvider for process lifecycle, and a LlamaCppRuntime for availability, benchmark, launch, health, stop, and proxy metadata. Existing domain scheduling continues to operate on normalized pool/route records; local llama.cpp routes become one runtime-backed route type rather than a scheduler special case.

**Tech Stack:** Python 3.11 stdlib, `subprocess`, `urllib.request`, `http.server`, JSON state, pytest tests.

---

### Task 1: Adapter Interfaces And Config

**Files:**
- Create: `tests/test_local_runtime.py`
- Create: `anygpu/config.py`
- Create: `anygpu/runtime.py`

- [x] Write tests for default config, env overrides, port allocation, local pool shape, and llama.cpp binary detection.
- [x] Run `python -m pytest tests/test_local_runtime.py -q` and verify failure due to missing modules.
- [x] Implement config and runtime adapter primitives.
- [x] Re-run the test and verify pass.

### Task 2: Real/Simulated Route Selection

**Files:**
- Modify: `tests/test_local_runtime.py`
- Modify: `anygpu/domain.py`
- Modify: `anygpu/cli.py`

- [x] Write tests for `anygpu compute verify local`, GGUF local benchmark metadata, and non-GGUF simulated fallback metadata.
- [x] Run targeted tests and verify failure.
- [x] Wire local compute verification and benchmark route creation through the runtime adapter.
- [x] Re-run targeted tests and verify pass.

### Task 3: Process Lifecycle

**Files:**
- Create: `tests/fixtures/fake_llama_server.py`
- Create: `anygpu/provider.py`
- Modify: `anygpu/domain.py`
- Modify: `anygpu/cli.py`

- [x] Write tests that launch a fake llama.cpp-compatible server, store pid/port/log path metadata, health-check it, and stop it with `anygpu deployments stop`.
- [x] Run targeted tests and verify failure.
- [x] Implement LocalProvider process launch, health-check, stop, and log capture.
- [x] Re-run targeted tests and verify pass.

### Task 4: Gateway Proxy

**Files:**
- Modify: `tests/test_gateway.py`
- Modify: `anygpu/gateway.py`

- [x] Write tests that local llama.cpp deployments proxy `/v1/chat/completions` to the local runtime and always include route metadata headers.
- [x] Run targeted tests and verify failure.
- [x] Implement proxying for non-simulated local llama.cpp routes, preserve simulated response behavior for all other routes, and add headers.
- [x] Re-run targeted tests and verify pass.

### Task 5: Docs And Verification

**Files:**
- Modify: `README.md`

- [x] Document config keys, local verify, GGUF registration, local benchmark, serve, gateway proxying, and stop flow.
- [x] Run `python -m pytest -q`.
- [x] Run CLI smoke checks for local simulated fallback and process lifecycle using the fake server.
