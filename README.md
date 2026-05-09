# AnyGPU Local V1

This repo contains a fully functional local prototype of the production AnyGPU flow:

1. Connect managed or BYOC compute.
2. Verify hardware/runtime compatibility.
3. Register a model.
4. Profile workload requirements.
5. Benchmark candidate placements.
6. Create a deployment policy.
7. Serve an OpenAI-compatible endpoint.
8. Monitor status, logs, metrics, costs, fallback, and optimization.

State is stored in `ANYGPU_HOME/state.json`. If `ANYGPU_HOME` is unset, the CLI uses `.anygpu/state.json`.

## Crucible Compute agent layer

This repo also includes a dependency-free Crucible Compute backend layer on top of AnyGPU:

- SQLite-backed signup/login/session persistence under `ANYGPU_HOME/crucible.sqlite3`.
- Natural-language deployment planning for the hackathon demo prompt, including Qwen 7B profiling, provider recommendation, uncertainty, and Nia-style context snippets.
- Explicit approval gate before any paid GPU launch path.
- Simulated approved deployment records with endpoint URL, logs, health checks, benchmark data, status, and stop flow.
- Honest provider capability reporting for Modal, SkyPilot, Lambda Cloud, and CoreWeave based on local credentials/support.
- CLI commands and an MCP-style tool dispatcher for personal-agent workflows.

Run the CLI flow:

```bash
export ANYGPU_HOME=.local-anygpu

USER_JSON=$(python -m anygpu crucible signup \
  --email admin@example.com \
  --password demo-password \
  --role admin)

USER_ID=$(printf '%s' "$USER_JSON" | python -c 'import json, sys; print(json.load(sys.stdin)["id"])')

PLAN_JSON=$(python -m anygpu crucible plan \
  --user-id "$USER_ID" \
  --prompt "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.")

PLAN_ID=$(printf '%s' "$PLAN_JSON" | python -c 'import json, sys; print(json.load(sys.stdin)["id"])')

python -m anygpu crucible deploy --plan-id "$PLAN_ID"

APPROVAL_JSON=$(python -m anygpu crucible approve \
  --plan-id "$PLAN_ID" \
  --user-id "$USER_ID")

APPROVAL_TOKEN=$(printf '%s' "$APPROVAL_JSON" | python -c 'import json, sys; print(json.load(sys.stdin)["token"])')

DEPLOYMENT_JSON=$(python -m anygpu crucible deploy \
  --plan-id "$PLAN_ID" \
  --approval-token "$APPROVAL_TOKEN")

DEPLOYMENT_ID=$(printf '%s' "$DEPLOYMENT_JSON" | python -c 'import json, sys; print(json.load(sys.stdin)["id"])')

python -m anygpu crucible status --deployment-id "$DEPLOYMENT_ID"
python -m anygpu crucible logs --deployment-id "$DEPLOYMENT_ID"
python -m anygpu crucible health --deployment-id "$DEPLOYMENT_ID"
python -m anygpu crucible stop --deployment-id "$DEPLOYMENT_ID"
```

Discover and call the same backend actions through the MCP-style tool surface:

```bash
python -m anygpu crucible mcp-tools
python -m anygpu crucible mcp-call crucible_list_provider_capabilities
python -m anygpu crucible mcp-call crucible_search_context \
  --arguments-json '{"query":"Qwen 7B cheapest GPU health check"}'
```

## Quickstart

```bash
export ANYGPU_HOME=.local-anygpu

python -m anygpu login --email ops@acme.test
python -m anygpu org create acme-ai
python -m anygpu project create prod-chat

python -m anygpu compute use managed
python -m anygpu compute connect kubernetes --name acme-prod-k8s --context prod-cluster --namespace anygpu
python -m anygpu compute connect docker --name local-docker
python -m anygpu compute inventory local-docker
python -m anygpu compute inventory acme-prod-k8s
python -m anygpu compute verify nvidia-fast
python -m anygpu compute verify acme-prod-k8s
python -m anygpu compute pools list

python -m anygpu model register qwen-prod --source hf:Qwen/Qwen3-32B --format safetensors --task chat
python -m anygpu profile qwen-prod --traffic 50qps --context 8192 --output-tokens-p50 512 --latency-p95 900ms
python -m anygpu benchmark qwen-prod --policy balanced --targets managed:nvidia-fast,byoc:acme-prod-k8s --duration 10m

python -m anygpu policy create prod-chat-policy --objective cheapest --max-p95 900ms --fallback required --regions us-west,us-east --prefer byoc --allow-managed-overflow true
python -m anygpu serve qwen-prod --name support-chat-prod --policy prod-chat-policy --runtime auto --replicas min=2,max=20 --endpoint openai

python -m anygpu deployments status support-chat-prod
python -m anygpu metrics support-chat-prod
python -m anygpu costs support-chat-prod
python -m anygpu optimize support-chat-prod
```

## Managed provider broker

Managed AnyGPU capacity is represented through a provider broker catalog. This is the control-plane layer that will eventually hold AnyGPU-managed provider accounts, price feeds, capacity checks, quotas, and provisioning status. The current implementation combines a seeded catalog with live price/capacity refresh adapters for selected providers.

Seed the broker:

```bash
python -m anygpu broker refresh
```

Inspect managed providers by architecture:

```bash
python -m anygpu providers list
python -m anygpu providers list --architecture nvidia
python -m anygpu providers list --architecture amd
python -m anygpu providers list --architecture tpu
python -m anygpu providers list --architecture intel-gaudi
python -m anygpu providers list --architecture apple-silicon
```

The seeded provider catalog covers:

```text
NVIDIA
  RunPod, Lambda Cloud, Vast.ai, Vultr, AWS EC2 GPU, Google Cloud GPU,
  Azure GPU, CoreWeave, Crusoe Cloud, Fluidstack

AMD
  TensorWave, Azure GPU, Vast.ai, Vultr

Google TPU
  Google Cloud TPU

Intel Gaudi / Intel XPU
  Intel Developer Cloud, AWS EC2 Gaudi

Apple Silicon
  MacStadium, AWS Mac, Scaleway Apple Silicon
```

Inspect seeded price and capacity records:

```bash
python -m anygpu prices list --accelerator h100
python -m anygpu prices list --architecture tpu
python -m anygpu capacity list --architecture amd
```

Refresh live Vast.ai marketplace offers into broker records:

```bash
export VAST_AI_API_KEY=...

python -m anygpu prices refresh \
  --provider vast \
  --accelerator h100 \
  --limit 100
```

The Vast adapter calls the search-offers API and normalizes returned offers into:

```text
provider_broker.price_records
provider_broker.capacity_records
```

The refresh records include the Vast offer ID, GPU name, normalized accelerator, architecture, region/geolocation, GPU count, memory, hourly price, reliability, CUDA/driver metadata when present, and availability. It does not provision instances yet.

Refresh live Vultr Cloud GPU and Bare Metal plans into broker records:

```bash
export VULTR_API_KEY=...

python -m anygpu prices refresh \
  --provider vultr \
  --accelerator a100 \
  --limit 100
```

The Vultr adapter calls the plans APIs for Cloud GPU (`type=vcg`) and Bare Metal, then normalizes returned plans into the same:

```text
provider_broker.price_records
provider_broker.capacity_records
```

The refresh records include the Vultr plan ID, deployment kind (`cloud-gpu` or `bare-metal`), normalized accelerator, architecture, region, GPU count, memory, hourly price derived from monthly cost when present, and availability inferred from listed plan locations.

Seeded records use explicit status fields:

```text
price_status=seeded
capacity_status=unknown
quota_status=not_checked
provisioning_status=not_configured
credential_status=deployment_secret_required
```

This keeps the product contract honest: AnyGPU knows which managed providers and accelerators it intends to broker, but a route is not live-provisionable until provider credentials, quota checks, and capacity APIs are wired.

`compute use managed` now registers both the original simulator pools and broker-derived managed pools such as:

```text
managed-h100-runpod-us-secure
managed-a100-vultr-cloud-gpu
managed-mi355x-vultr-bare-metal
managed-mi300x-tensorwave-us-east
managed-tpu-v5e-gcp-us-central1
managed-gaudi-intel-us
managed-m4-macstadium-us
```

## Provider inventory

Docker registration discovers the local Docker daemon, host GPU inventory when available, and supported runtime families:

```bash
python -m anygpu compute connect docker --name local-docker
python -m anygpu compute inventory local-docker
```

The inventory command returns a normalized provider object:

```json
{
  "provider": "docker",
  "node_id": "local",
  "gpus": [],
  "runtimes_supported": ["llama.cpp", "pytorch", "vllm"]
}
```

If `nvidia-smi` is available on the host, AnyGPU records NVIDIA GPU name, memory, driver, and CUDA availability. If Docker or GPU discovery is unavailable, the command still returns the same schema with `status: "unavailable"` or an empty `gpus` list.

Kubernetes BYOC registration records the configured context and namespace:

```bash
python -m anygpu compute connect kubernetes \
  --name acme-prod-k8s \
  --context prod-cluster \
  --namespace anygpu

python -m anygpu compute inventory acme-prod-k8s
```

When `kubectl` can reach the context, AnyGPU lists nodes and normalizes GPU resources such as `nvidia.com/gpu`, `amd.com/gpu`, and `gpu.intel.com/i915`:

```json
{
  "provider": "kubernetes",
  "cluster": "acme-prod-k8s",
  "context": "prod-cluster",
  "namespace": "anygpu",
  "status": "available",
  "nodes": [
    {
      "name": "gpu-node-1",
      "available": true,
      "accelerators": [
        {
          "vendor": "nvidia",
          "name": "NVIDIA L4",
          "count": 4,
          "allocatable": 3,
          "memory_gb": 24,
          "resource": "nvidia.com/gpu"
        }
      ],
      "runtimes": ["vllm", "sglang", "pytorch", "llama.cpp"]
    }
  ],
  "runtime_support": ["vllm", "sglang", "pytorch", "llama.cpp"]
}
```

If `kubectl` is missing or no context is configured, inventory returns the same object shape with `status: "unavailable"` and an error. `compute verify` then preserves the existing simulated BYOC certification path and marks compatibility records with `simulated=true`; with a reachable context it records `simulated=false`.

Dockerized llama.cpp serving uses `ghcr.io/ggml-org/llama.cpp:server` by default. Override it with:

```bash
python -m anygpu config set docker_llama_cpp_image ghcr.io/ggml-org/llama.cpp:server
```

Start a GGUF model through the Docker provider:

```bash
python -m anygpu serve start qwen-local \
  --model ./models/qwen.gguf \
  --runtime llama.cpp \
  --compute local-docker
```

Then call the container's OpenAI-compatible endpoint:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local",
    "messages": [{"role": "user", "content": "Say hello in one sentence."}]
  }'
```

Operate the Docker serve runtime:

```bash
python -m anygpu serve ps
python -m anygpu serve logs qwen-local
python -m anygpu serve stop qwen-local
```

For HF/safetensors models on a CUDA-capable Docker host, the same Docker provider can compile a vLLM runtime command:

```bash
python -m anygpu serve start qwen-vllm \
  --model hf:Qwen/Qwen2.5-7B-Instruct \
  --runtime vllm \
  --compute local-docker
```

This uses `vllm/vllm-openai:latest`, maps the selected host port to container port `8000`, passes `--gpus all`, and exposes `/v1/chat/completions`.

## Vultr cloud deployment

Vultr is the first cloud provisioning adapter. It can create a Cloud GPU instance or Bare Metal resource, attach cloud-init user data, start Docker on boot, and run a vLLM or llama.cpp server container.

Configure the key:

```bash
VULTR_API_KEY=...
```

Register a Vultr compute pool:

```bash
python -m anygpu login
python -m anygpu org create acme-ai
python -m anygpu project create prod-chat
python -m anygpu compute connect vultr --name vultr-prod
```

Refresh live plan data:

```bash
python -m anygpu prices refresh --provider vultr --limit 100
python -m anygpu prices list --accelerator a100
```

Create a paid Vultr runtime explicitly:

```bash
python -m anygpu serve start qwen-vultr \
  --model hf:Qwen/Qwen2.5-7B-Instruct \
  --runtime vllm \
  --compute vultr-prod \
  --plan vcg-a16-6c-64g-16vram \
  --region ewr \
  --os-id 2284 \
  --confirm-cost
```

`--confirm-cost` is required for Vultr because this command creates billable cloud resources. The deployment stores the Vultr resource ID, plan, region, runtime port, upstream URL when Vultr returns a public IP, and `simulated=false`.

Stop and delete the Vultr resource:

```bash
python -m anygpu serve stop qwen-vultr
```

Current Vultr limits:

```text
Implemented:
  create Cloud GPU instances
  create Bare Metal instances when the selected plan starts with vbm-
  cloud-init Docker bootstrap for vLLM and llama.cpp
  delete resource on serve stop

Not implemented yet:
  SSH log streaming
  firewall/security group creation
  readiness polling until model server is fully healthy
  managed domain/TLS
```

## Vast cloud deployment

Vast is the first marketplace-style provisioning adapter. It searches verified rentable offers, selects a matching offer under the requested price cap, creates an instance through the Vast API, starts a runtime with Vast `onstart`, stores the contract ID and public upstream metadata, and destroys the instance on `serve stop`.

Configure the key:

```bash
VAST_AI_API_KEY=...
```

Register a Vast compute pool:

```bash
python -m anygpu compute connect vast --name vast-prod
```

Refresh live offers:

```bash
python -m anygpu prices refresh --provider vast --accelerator rtx-4090 --limit 20
python -m anygpu prices list --accelerator rtx-4090
```

Create a paid Vast runtime explicitly:

```bash
python -m anygpu serve start vast-4090-smoke \
  --model hf:Qwen/Qwen2.5-0.5B-Instruct \
  --runtime vllm \
  --compute vast-prod \
  --accelerator rtx-4090 \
  --max-price 0.35 \
  --disk-gb 30 \
  --confirm-cost
```

`--confirm-cost` is required for Vast because this command creates billable marketplace resources. Vast may reject instance creation if the API key does not have create privileges from a 2FA-authenticated account/session.

Stop and destroy the Vast instance:

```bash
python -m anygpu serve stop vast-4090-smoke
```

Current Vast limits:

```text
Implemented:
  search verified on-demand offers
  cap offer selection by max hourly price
  create vLLM or llama.cpp runtime instance
  map Vast exposed runtime port into AnyGPU upstream URL
  destroy instance on serve stop

Not implemented yet:
  SSH bootstrap/log streaming
  retry next offer if a selected offer disappears
  readiness polling until the model server is fully healthy
  artifact sync for training jobs
```

Run a raw model/runtime/compute benchmark:

```bash
python -m anygpu benchmark run \
  --model ./models/qwen.gguf \
  --runtime llama.cpp \
  --compute local-docker \
  --profile latency-chat
```

The benchmark runner launches a temporary Docker runtime, sends an OpenAI-compatible chat request, records measured latency and estimated tokens/sec into `benchmark_results`, and stops/removes the container. Supported initial profiles are `latency-chat`, `throughput-chat`, and `long-context`.

Each non-simulated benchmark also upserts normalized compatibility data:

```text
model_records
hardware_nodes
runtime_profiles
compatibility_records
```

Successful benchmark runs create `status: verified` compatibility records. Failed benchmark measurements create `status: failed` records with the benchmark error attached. This is the first factual compatibility database path; manually verified compute records still exist for the earlier simulator flow.

Schedule from verified benchmark records:

```bash
python -m anygpu costs set \
  --compute local-docker \
  --per-1m-tokens 0.12 \
  --label local-test-cost

python -m anygpu deploy qwen-prod \
  --model ./models/qwen.gguf \
  --sla latency \
  --strategy cheapest-compatible

python -m anygpu explain qwen-prod
```

The scheduler only considers benchmark-sourced `verified` compatibility records for this path. The explanation includes the selected compute, hardware, runtime, benchmark latency, throughput, estimated cost, and compatibility record ID.

Cost records are stored separately from usage events. Docker defaults to `local/free`, but `costs set` can override the scheduler-facing cost for any registered compute pool.

Generate Kubernetes manifests from the same deployment inputs:

```bash
python -m anygpu deploy qwen-prod \
  --model hf:Qwen/Qwen2.5-7B-Instruct \
  --runtime vllm \
  --target kubernetes \
  --gpu nvidia-l4 \
  --namespace anygpu \
  --replicas 1
```

This renders ConfigMap, PersistentVolumeClaim, Deployment, and Service YAML. The manifest is stored in `kubernetes_manifests` but is not applied to a cluster yet.

## Real local llama.cpp path

AnyGPU now has one partially real execution path: local llama.cpp serving for GGUF models. The scheduler still uses normalized routes, so local llama.cpp is an execution adapter rather than a scheduler special case.

Supported config keys:

```text
llama_cpp_server_path
llama_cpp_server_args
llama_cpp_cli_path
llama_cpp_cli_args
llama_cpp_health_path
llama_cpp_ctx_size
model_cache_path
local_runtime_host
local_runtime_port_start
local_runtime_port_end
```

You can set them with environment variables:

```bash
export ANYGPU_HOME=.local-anygpu
export ANYGPU_LLAMA_CPP_SERVER_PATH=/path/to/llama-server
export ANYGPU_LLAMA_CPP_CLI_PATH=/path/to/llama-cli
export ANYGPU_MODEL_CACHE_PATH=.local-anygpu/models
export ANYGPU_LLAMA_CPP_HEALTH_PATH=/health
export ANYGPU_LOCAL_RUNTIME_HOST=127.0.0.1
export ANYGPU_LOCAL_RUNTIME_PORT_START=18080
export ANYGPU_LOCAL_RUNTIME_PORT_END=18280
```

For builds where the server is launched through another executable, pass fixed leading args:

```bash
export ANYGPU_LLAMA_CPP_SERVER_PATH=/usr/bin/python3
export ANYGPU_LLAMA_CPP_SERVER_ARGS="/path/to/server-wrapper.py"
```

The same keys can be persisted in state:

```bash
python -m anygpu config set llama_cpp_server_path /path/to/llama-server
python -m anygpu config set llama_cpp_cli_path /path/to/llama-cli
python -m anygpu config set llama_cpp_health_path /health
python -m anygpu config set llama_cpp_ctx_size 8192
python -m anygpu config set model_cache_path .local-anygpu/models
python -m anygpu config set local_runtime_host 127.0.0.1
python -m anygpu config set local_runtime_port_start 18080
python -m anygpu config set local_runtime_port_end 18280
```

The server launcher builds commands in this shape:

```bash
/path/to/llama-server \
  -m ./models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 \
  --port <allocated_port> \
  --ctx-size 8192
```

Verify local llama.cpp compatibility:

```bash
python -m anygpu compute verify local
```

Register a GGUF model:

```bash
python -m anygpu model register local-qwen-gguf \
  --source /absolute/path/to/qwen2.5-7b-q4_k_m.gguf \
  --format gguf \
  --runtime llama.cpp \
  --task chat
```

Run a local benchmark:

```bash
python -m anygpu benchmark local-qwen-gguf --targets local --duration 1m
```

If the model is GGUF, the model file exists, and llama.cpp is available, the benchmark launches a temporary llama.cpp server, sends a real OpenAI-compatible chat prompt, records latency/tokens/sec/token-count method/logs, and marks the result `simulated=false`. If llama.cpp is unavailable or the model is not GGUF, AnyGPU preserves the simulator path and marks the route `simulated=true`.

Create a local policy and serve:

```bash
python -m anygpu policy create local-policy \
  --objective fastest \
  --max-p95 2000ms \
  --fallback optional

python -m anygpu serve local-qwen-gguf \
  --name local-chat \
  --policy local-policy
```

For a real local llama.cpp route, `serve` launches a local runtime process and stores process metadata in state:

```text
runtime
provider
pid
host
port
upstream_url
model_path
started_at
health
health_path
health_check_type
logs_path
simulated
```

Inspect and clean runtime processes:

```bash
python -m anygpu runtime ps
python -m anygpu runtime cleanup
```

Stop the local runtime cleanly:

```bash
python -m anygpu deployments stop local-chat
```

Start the local gateway:

```bash
export ANYGPU_HOME=.local-anygpu
python -m anygpu gateway --host 127.0.0.1 --port 8765
```

Call it with an OpenAI-compatible request:

```bash
curl http://127.0.0.1:8765/v1/chat/completions \
  -H "Authorization: Bearer local" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "support-chat-prod",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Gateway responses include route metadata headers:

```text
x-anygpu-deployment
x-anygpu-route
x-anygpu-runtime
x-anygpu-simulated
x-anygpu-upstream
```

For non-simulated local llama.cpp routes, the gateway proxies `/v1/chat/completions` to the launched llama.cpp server. Simulated managed/BYOC routes keep the existing local simulator response path.

## End-to-end real local example

```bash
export ANYGPU_HOME=.local-anygpu

python -m anygpu login --email ops@acme.test
python -m anygpu org create acme-ai
python -m anygpu project create prod-chat

python -m anygpu config set llama_cpp_server_path /path/to/llama-server
python -m anygpu config set llama_cpp_health_path /health
python -m anygpu config set model_cache_path ./models
python -m anygpu config set local_runtime_host 127.0.0.1
python -m anygpu config set local_runtime_port_start 18080
python -m anygpu config set local_runtime_port_end 18280

python -m anygpu compute verify local

python -m anygpu model register qwen-small \
  --source ./models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  --format gguf \
  --task chat \
  --runtime llama.cpp

python -m anygpu benchmark qwen-small --targets local

python -m anygpu policy create prod-chat-policy \
  --objective fastest \
  --max-p95 2000ms \
  --fallback optional

python -m anygpu serve qwen-small \
  --name qwen-local-prod \
  --policy prod-chat-policy \
  --runtime llama.cpp \
  --endpoint openai

python -m anygpu gateway --host 127.0.0.1 --port 8765
```

Then call:

```bash
curl http://127.0.0.1:8765/v1/chat/completions \
  -H "Authorization: Bearer local" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-local-prod",
    "messages": [{"role":"user","content":"Say hello in one sentence."}]
  }'
```

## Scope

This v1 is functional locally and can launch one real runtime path: local llama.cpp serving for GGUF models. It does not install Kubernetes agents, perform real GPU scheduling, launch managed cloud containers, call external cloud providers, or integrate real billing. Those remain represented through normalized pool records, verification records, benchmark results, route selection, and gateway routing.
