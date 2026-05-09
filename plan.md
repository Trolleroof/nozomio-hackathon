# Plan: Cheapest Compute Finder + Qwen 2.5-7B Deployer

## Goal

Build an MCP server + Claude agent that:
1. Queries multiple GPU cloud providers for current pricing and availability
2. Picks the cheapest viable option for running Qwen 2.5-7B
3. Automatically deploys Qwen 2.5-7B served via vLLM (OpenAI-compatible API)
4. Monitors cost and can tear down the instance on demand

---

## Target Model

- **Model:** Qwen/Qwen2.5-7B-Instruct
- **Minimum VRAM:** ~16 GB (fits on a single A10G, A100-40G, 3090, 4090, or similar)
- **Serving stack:** vLLM with `--served-model-name qwen` exposing `/v1/chat/completions`

---

## Providers to Compare

| Provider     | API Docs                        | Notes                              |
|--------------|---------------------------------|------------------------------------|
| Lambda Labs  | cloud.lambdalabs.com/api/v1     | Spot + on-demand, good A10G supply |
| RunPod       | api.runpod.io/graphql           | Spot pods, cheapest $/hr often     |
| Vast.ai      | console.vast.ai/api/v0          | Auction-style, very cheap          |
| Modal        | modal.com SDK                   | Serverless GPU, pay-per-second     |
| Railway      | railway.app (no GPU currently)  | CPU only — exclude from GPU search |

> Note: Railway does not offer GPU instances. It will be used only if a CPU-quantized fallback (e.g. Q4 GGUF via llama.cpp) is in scope. For now, exclude from GPU comparison.

---

## Architecture

```
User / Claude Agent
       │
       ▼
  MCP Server (Python, FastMCP or mcp SDK)
  ├── tool: list_gpu_prices()       → polls all providers, returns sorted list
  ├── tool: check_availability()    → filters to instances with enough VRAM
  ├── tool: deploy_cheapest()       → provisions cheapest available + runs vLLM
  ├── tool: get_endpoint()          → returns OpenAI-compatible base URL + key
  ├── tool: get_spend()             → current running cost / uptime
  └── tool: teardown()             → destroys instance
       │
       ▼
  Deployed Instance
  └── vLLM server  →  POST /v1/chat/completions
```

---

## MCP Server Implementation Plan

### Phase 1 — Price Aggregator

**File:** `mcp_server/providers/`

- `lambda_labs.py` — GET `/instances` for on-demand pricing
- `runpod.py` — GraphQL query for community cloud spot pods
- `vast_ai.py` — GET `/bundles` with filters (VRAM ≥ 16 GB, reliability > 0.95)
- `modal_gpu.py` — use Modal SDK to estimate cost per GPU-hour

Each provider module returns a normalized `GpuOffer` dataclass:
```python
@dataclass
class GpuOffer:
    provider: str        # "lambda", "runpod", "vast", "modal"
    instance_id: str
    gpu_type: str        # "A10G", "A100", "RTX4090", etc.
    gpu_count: int
    vram_gb: int
    price_per_hr: float  # USD
    available: bool
    region: str
```

**MCP tool `list_gpu_prices`** — calls all modules in parallel, merges, sorts by `price_per_hr`, returns top 10.

### Phase 2 — Deployment

**File:** `mcp_server/deploy.py`

- Pick the top (cheapest) available offer from Phase 1
- Provider-specific provisioning:
  - **Lambda Labs:** POST `/instance-operations/launch` with SSH key
  - **RunPod:** GraphQL `podFindAndDeployOnDemand` mutation
  - **Vast.ai:** POST `/asks/{id}/` to accept an offer
  - **Modal:** spawn a `modal.App` with `gpu="A10G"` and run vLLM container
- After instance is up, SSH in (or use provider SDK) and run:
  ```bash
  pip install vllm
  vllm serve Qwen/Qwen2.5-7B-Instruct \
    --served-model-name qwen \
    --host 0.0.0.0 --port 8000 \
    --api-key $VLLM_API_KEY
  ```
- Poll until `/v1/models` returns 200, then surface the endpoint URL.

### Phase 3 — Monitoring & Teardown

- `get_spend()` — calculates `uptime_hours * price_per_hr` from deploy timestamp
- `teardown()` — calls provider delete/terminate API, confirms instance gone

---

## MCP Server Setup

**Stack:** Python 3.11+, `mcp` SDK (Anthropic), `httpx` for async HTTP, `paramiko` or `asyncssh` for SSH bootstrapping.

```
mcp_server/
├── server.py           # FastMCP app, registers all tools
├── providers/
│   ├── __init__.py
│   ├── lambda_labs.py
│   ├── runpod.py
│   ├── vast_ai.py
│   └── modal_gpu.py
├── deploy.py
├── monitor.py
├── models.py           # GpuOffer dataclass
└── requirements.txt
```

**Run:**
```bash
python server.py   # exposes MCP over stdio for Claude Desktop / Claude Code
```

---

## Credentials (Pre-configured)

The server reads from environment variables — assumed already set:

| Variable               | Provider   |
|------------------------|------------|
| `LAMBDA_API_KEY`       | Lambda Labs |
| `RUNPOD_API_KEY`       | RunPod      |
| `VAST_API_KEY`         | Vast.ai     |
| `MODAL_TOKEN_ID`       | Modal       |
| `MODAL_TOKEN_SECRET`   | Modal       |
| `VLLM_API_KEY`         | Generated locally, injected into vLLM |

---

## Agent Workflow (End-to-End)

1. User asks: *"Deploy Qwen as cheaply as possible"*
2. Agent calls `list_gpu_prices()` → gets sorted offers
3. Agent calls `deploy_cheapest()` → provisions top offer, bootstraps vLLM
4. Agent calls `get_endpoint()` → returns `{"base_url": "http://...:8000/v1", "api_key": "..."}`
5. User can now hit the OpenAI-compatible endpoint directly
6. Agent can call `get_spend()` anytime to show cost so far
7. User says *"shut it down"* → agent calls `teardown()`

---

## Milestones

| # | Task                                      | Done |
|---|-------------------------------------------|------|
| 1 | Scaffold MCP server with FastMCP          | [ ]  |
| 2 | Implement Lambda Labs price fetcher       | [ ]  |
| 3 | Implement RunPod price fetcher            | [ ]  |
| 4 | Implement Vast.ai price fetcher           | [ ]  |
| 5 | Implement Modal cost estimator            | [ ]  |
| 6 | `list_gpu_prices` tool (aggregator)       | [ ]  |
| 7 | Deploy logic for Lambda Labs              | [ ]  |
| 8 | Deploy logic for RunPod                   | [ ]  |
| 9 | Deploy logic for Vast.ai                  | [ ]  |
| 10| Deploy logic for Modal                    | [ ]  |
| 11| vLLM bootstrap script                     | [ ]  |
| 12| `get_endpoint`, `get_spend`, `teardown`   | [ ]  |
| 13| Wire into Claude Desktop via MCP config   | [ ]  |
| 14| End-to-end test: cheapest → deployed      | [ ]  |
