Codex /goal: Crucible Compute — Hackathon-Optimized Build Plan

Build Crucible Compute, a production-deployed agentic SaaS that lets a user or personal agent request an open-source Hugging Face text-generation model and receive a live OpenAI-compatible inference endpoint on GPU infrastructure.

The app must be usable by someone outside the team through a public URL with authentication, a real backend, persistent database state, deployment logs, health checks, and an agent that handles off-script user requests.

Winning constraint

Do not optimize for maximum provider breadth first.

Optimize for this demo:

A stranger signs up,
types “Deploy Qwen 7B cheaply,”
Crucible profiles the model,
compares GPU/provider options,
explains the recommendation,
asks for approval,
deploys a real vLLM endpoint,
runs health checks,
shows logs and benchmark results,
lets the user test it in a playground,
and exposes the same workflow through MCP for Hermes/OpenClaw/getfolk/Poke-style agents.

The rubric heavily rewards:

Production readiness
Agent reliability
Full-stack depth
Clear live demo
Judge excitement

So every implementation phase must improve at least one of those.

1. Rubric-driven priorities

Create docs/RUBRIC_STRATEGY.md with this exact scoring strategy.

Production Readiness

Target the “5 - Exceptional” column.

Required:

- Public deployed URL, not localhost.
- Real signup/login.
- Protected dashboard.
- Real database.
- Real deployment records.
- Real backend/worker.
- Real provider integration.
- Real endpoint for at least one model/provider path.
- Logs and errors visible in dashboard.
- Stop/teardown button.
- Health checks before marking deployment ready.
- Abuse guardrails for managed provider accounts.

Production-readiness shortcuts are allowed only if they keep the app usable by strangers.

InsForge should be attempted first because it provides PostgreSQL, JWT auth, storage, and agent-friendly endpoints out of the box. If InsForge setup blocks progress for more than one hour, fall back to Supabase Auth + Postgres. Do not lose the hackathon over backend scaffolding.

Agent Reliability

Target the “5 - Exceptional” column.

Required:

- Agent handles messy natural-language deployment requests.
- Agent never hallucinates unsupported provider support.
- Agent explains uncertainty.
- Agent asks for approval before paid actions.
- Agent handles missing model IDs, oversized models, private HF models, unsupported providers, unavailable GPUs, failed health checks, and stop requests.
- Nia is used to ground the agent in the repo, docs, provider notes, deployment logs, and known working recipes.

Nia must be a core reliability feature, not just a sponsor checkbox. Nia supports CLI, MCP Server, Agent Skill, and other setups for agent workflows.

Full-Stack Depth

Target the “4 or 5” column.

Required:

- Frontend dashboard.
- Backend API.
- Auth.
- Database.
- Python or Node worker.
- Provider/SkyPilot integration.
- Agent planner.
- MCP server.
- CLI.
- Nia context layer.
- Logs, health checks, benchmark records.
Demo and Presentation

Target the “5 - Exceptional” column.

Required:

- Demo starts from a public URL.
- Show signup/login.
- Show one natural-language model deployment request.
- Show agent plan and explanation.
- Show approval gate.
- Show logs streaming.
- Show endpoint becoming ready.
- Show playground response.
- Show MCP tool call.
- Show stop/teardown.
Judge’s Personal Rating

Target excitement.

The story:

“Crucible gives every AI agent a hardware-agnostic GPU backend. Hermes, OpenClaw, getfolk, or Poke can call one MCP tool and get a real OpenAI-compatible endpoint without knowing anything about Lambda, Prime Intellect, CoreWeave, Modal, vLLM, or GPU sizing.”
2. Major adjustment from previous plan

The previous plan was too broad for a one-day production-grade hackathon.

Replace it with this priority stack:

Priority 1:
Live app with auth, database, and production deployment.

Priority 2:
One real end-to-end model deployment path.

Priority 3:
Nia-grounded agent reliability.

Priority 4:
MCP so other agents can use Crucible.

Priority 5:
Provider comparison.

Priority 6:
More provider adapters.

Do not build a large multi-provider platform before proving that one user can deploy one model end-to-end.

3. Provider strategy: SkyPilot-first, but time-boxed

Use this decision rule.

First attempt: SkyPilot

Codex should first try to use SkyPilot because it is closest to the real Crucible vision: hardware-agnostic GPU orchestration. It supports many clouds and can schedule on available/cheap infra.

Use SkyPilot for:

- Lambda Cloud
- Prime Intellect
- CoreWeave
- Kubernetes if configured
- provider comparison
- deployment YAML generation
- logs/status
- teardown

But Codex must not get stuck.

Time box

Set a strict time box:

SkyPilot dry-run working: 60 minutes max
SkyPilot live tiny-model deploy working: 90 additional minutes max

If SkyPilot live deploy is blocked, switch to fallback.

Fallback: Modal direct deploy

Use Modal direct deploy if SkyPilot blocks production-readiness.

Modal fallback still preserves the core story because:

- User still requests a model.
- Agent still profiles and plans.
- System still deploys vLLM.
- Endpoint is still OpenAI-compatible.
- Dashboard, auth, database, logs, health checks, MCP, and Nia still work.

Modal’s docs include an OpenAI-compatible vLLM deployment example, so it is a practical fallback for “ship today.”

What not to do

Do not spend half the hackathon patching SkyPilot unless the patch is small and obvious.

Allowed:

- Patch SkyPilot config parsing.
- Patch provider naming.
- Patch CLI wrapper.
- Patch generated YAML.

Not allowed:

- Writing a new cloud backend from scratch.
- Debugging deep SkyServe internals for hours.
- Attempting full CoreWeave/Kubernetes setup if credentials or cluster access are missing.

SkyServe is useful, but it has rough edges for external production serving; the docs describe it as beta and better suited for internal serving use cases. So for the hackathon, treat SkyServe as the MVP path if it works, not as a hill to die on.

4. Final architecture

Use this production architecture:

Frontend:
- Next.js
- TypeScript
- Tailwind
- shadcn/ui
- Inter font
- deployed publicly on Vercel or InsForge deployment

Backend:
- InsForge if setup succeeds quickly
- Supabase fallback if InsForge blocks progress
- real auth
- real database
- protected API routes

Worker:
- Python FastAPI worker or Node worker
- deployed on Railway, Fly, Render, or a small VM
- must not run only on localhost
- handles SkyPilot/Modal deploy actions

GPU orchestration:
- SkyPilot first
- Modal fallback
- vLLM serving engine

Agent:
- structured planner
- Nia-grounded context retrieval
- deterministic approval gate
- no paid action without explicit approval

MCP:
- TypeScript MCP server
- deployed or runnable by external agents
- exposes planning, approval, deploy, status, logs, health, stop

CLI:
- thin wrapper over backend/MCP

Use Docker Compose only for local development, not final demo.

5. Auth and public-user safety

Because the app uses managed provider accounts, strangers cannot be allowed to freely spin up expensive GPUs.

Implement a hackathon safety policy:

Unauthenticated users:
- can see landing page only

Authenticated users:
- can create deployment plans
- can see estimates
- can run mock/demo planning
- can deploy only allowlisted tiny/safe models by default

Admin users:
- can approve live deployments
- can deploy larger models
- can stop any deployment

This is not product billing. It is abuse prevention for the hackathon.

Default safe model allowlist:

Qwen/Qwen2.5-0.5B-Instruct
Qwen/Qwen2.5-1.5B-Instruct
TinyLlama/TinyLlama-1.1B-Chat-v1.0

Show larger model plans, but require admin approval for live deploy:

Llama 8B
Qwen 7B
DeepSeek distill models
Llama 70B
Qwen 32B
6. Database schema changes

Use the previous schema, but add these hackathon-critical tables.

users

If using InsForge or Supabase, mirror auth user IDs into app state.

id uuid primary key,
email text not null,
role text not null default 'user', -- user | admin
created_at timestamptz default now()
agent_runs
id uuid primary key default gen_random_uuid(),
user_id uuid,
created_at timestamptz default now(),
source text not null, -- dashboard | cli | mcp
raw_input text not null,
parsed_intent jsonb,
status text not null, -- success | needs_clarification | error
nia_context_used jsonb,
model_output jsonb,
error text
provider_capabilities
id uuid primary key default gen_random_uuid(),
created_at timestamptz default now(),
provider text not null,
adapter text not null, -- skypilot | modal | manual | mock
status text not null, -- live | dry_run_only | configured | unsupported | failed
supports_deploy boolean default false,
supports_logs boolean default false,
supports_stop boolean default false,
supports_openai_endpoint boolean default false,
last_checked_at timestamptz,
last_error text,
metadata jsonb
demo_guardrails
id uuid primary key default gen_random_uuid(),
created_at timestamptz default now(),
key text not null unique,
value jsonb not null

Default values:

{
  "safe_model_allowlist": [
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct",
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
  ],
  "admin_approval_required_for_live_gpu": true,
  "max_non_admin_hourly_estimate_usd": 1.0,
  "default_autostop_minutes": 15
}
7. Agent behavior updates

The agent must be production-safe.

It can do
- Parse natural-language deployment requests.
- Search Nia for docs/context.
- Profile Hugging Face text-generation models.
- Estimate GPU requirements.
- Discover provider capabilities.
- Generate a deployment plan.
- Explain why it chose a provider/GPU.
- Ask clarifying questions.
- Create approval-required deployment plans.
- Trigger live deployment only with valid approval.
- Run health checks.
- Run evals.
- Suggest next steps after failure.
It cannot do
- Spend money without approval.
- Claim unsupported providers are live.
- Accept arbitrary shell commands.
- Deploy models outside allowlist for non-admins.
- Expose provider secrets.
- Mark a deployment ready before health checks pass.
Off-script handling examples

Add tests/agent/off_script_cases.json.

Test these prompts:

"deploy qwen cheap"
"give hermes a fast llama endpoint"
"i need newest deepseek but don't blow up cost"
"deploy gpt-4 on h100"
"deploy llama 70b on one cheap gpu"
"modal only"
"no modal, use pi or lambda"
"i don't care about cost, make it reliable"
"what model should I use for cheap code generation?"
"stop my deployment"
"why did this fail?"
"can getfolk call this via mcp?"
"make an endpoint but don't use multiple GPUs"

Each test must assert:

- parsed intent is valid or clarification is requested
- unsupported asks are not hallucinated
- paid actions are not executed
- response includes useful next action
8. Nia integration must be visible

Do not hide Nia in the backend.

Add a dashboard card:

Context used by agent
- SkyPilot docs
- vLLM docs
- repo deployment templates
- previous deployment logs
- known working recipes

Add a page:

/context

Show:

- Indexed sources
- Last sync time
- Recent Nia searches
- Context snippets used in agent decisions

Nia should index:

- Crucible repo
- SkyPilot docs
- vLLM docs
- Modal vLLM docs
- generated SkyPilot YAML templates
- deployment logs
- health-check failures
- benchmark summaries
- README/demo guide

Add tools:

crucible_search_context
crucible_index_deployment
crucible_explain_failure_with_context

Use Nia as cross-agent memory:

When Hermes deploys a model and gets an error, save the failure and resolution.
When OpenClaw later asks for a similar deploy, retrieve that context.
9. MCP must move earlier

Move MCP from a late phase to the middle of the build. The track rewards full-stack agents, and your product’s best story is that other agents can use it.

Required MCP tools:

crucible_plan_deployment
crucible_approve_plan
crucible_deploy_approved_plan
crucible_get_deployment_status
crucible_get_logs
crucible_run_health_check
crucible_stop_deployment
crucible_list_deployments
crucible_search_context
crucible_explain_failure

Add this to the dashboard:

Agent Access
- MCP server URL or command
- API token
- Example Hermes/OpenClaw config
- Example tool call

Example demo call:

{
  "tool": "crucible_plan_deployment",
  "arguments": {
    "prompt": "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
    "sourceAgent": "hermes"
  }
}

MCP deploy must fail without approval:

{
  "error": "Approval required before launching GPU resources."
}

This failure is a feature. It proves production-grade safety.

10. Updated implementation phases
Phase 0 — Production shell first

Goal: Public app with auth and DB before any GPU work.

Build:

- Next.js app
- Inter font
- Vercel-like UI
- InsForge backend if fast, Supabase fallback otherwise
- signup/login/logout
- protected dashboard
- deployments table
- agent_runs table
- provider_capabilities table
- STATUS.md
- README.md

Acceptance criteria:

- Public URL works.
- Stranger can sign up.
- Stranger can log in.
- Dashboard is protected.
- DB persists user and deployment records.

Tests:

- auth smoke test
- DB migration test
- protected route test
- deployment table CRUD test

Do not proceed until this is live.

Phase 1 — Mock full-stack deployment flow

Goal: Complete user flow with fake provider data.

Build:

- New deployment wizard
- Natural-language prompt input
- Model ID input
- objective selector: cheapest / reliable / low latency / balanced
- stop policy selector
- mock provider comparison
- scoring engine
- generated plan
- approval gate
- fake deployment timeline
- fake logs
- playground disabled with explanation

Acceptance criteria:

- User can type “Deploy Qwen 7B cheaply.”
- Agent creates a plan.
- UI shows provider/GPU recommendation.
- UI explains decision.
- Approval is required.
- Fake deployment reaches ready state.

Tests:

- scoring tests
- model profiler tests
- approval token tests
- off-script parser tests
Phase 2 — Nia integration and agent reliability

Goal: Make the agent grounded and robust before live deploy.

Build:

- Nia setup script
- Nia context search API route
- Nia context card in dashboard
- agent_runs logging
- off-script test suite
- failure explanation stub

Acceptance criteria:

- Agent can search indexed docs/context.
- Dashboard shows context used.
- Off-script tests pass.
- Agent does not hallucinate unsupported providers.

Tests:

pnpm test:agent
pnpm test:nia

If Nia credentials are not configured, app must degrade gracefully, but final demo should use Nia.

Phase 3 — Provider capability check

Goal: Decide the fastest real deployment path.

Build:

scripts/check-provider-capabilities.sh

It should check:

- SkyPilot installed
- SkyPilot API server reachable
- SkyPilot provider credentials configured
- Lambda available through SkyPilot
- Prime Intellect available through SkyPilot
- CoreWeave/Kubernetes available through SkyPilot
- Modal credentials configured
- vLLM image usable

Output:

{
  "skypilot": {
    "status": "configured",
    "supportsDryRun": true,
    "supportsLiveDeploy": false,
    "error": "..."
  },
  "modal": {
    "status": "configured",
    "supportsLiveDeploy": true
  }
}

Acceptance criteria:

- Dashboard provider page reflects real capability status.
- Unsupported providers are marked unsupported/pending.
- No fake live support.

Decision:

If SkyPilot live tiny-model deploy is viable, use SkyPilot for Phase 4.
If not, use Modal direct deploy for Phase 4 and keep SkyPilot as planning/dry-run.
Phase 4 — One real live deployment path

Goal: Deploy one real model end-to-end.

Preferred order:

1. SkyPilot to Lambda/Prime/CoreWeave if working
2. Modal direct vLLM deploy if SkyPilot blocks

Safe first model:

Qwen/Qwen2.5-0.5B-Instruct

Build:

- live deploy worker
- logs ingestion
- endpoint capture
- health check /v1/models
- health check /v1/chat/completions
- benchmark record
- stop/teardown
- playground enabled

Acceptance criteria:

- Authenticated admin can approve and deploy.
- Real GPU deployment starts.
- Endpoint appears in dashboard.
- Logs appear.
- Health check passes.
- Playground gets real response.
- Benchmark row is stored.
- Stop button tears down resources.

Tests:

- non-live integration tests
- live deploy test only when env-gated

Required live-test guards:

RUN_LIVE_DEPLOY_TESTS=true
LIVE_DEPLOY_APPROVED=true
DEFAULT_AUTOSTOP_MINUTES=15
Phase 5 — MCP and CLI

Goal: Make Crucible usable by personal agents.

Build:

- MCP server
- CLI wrapper
- dashboard Agent Access page
- API token generation
- MCP audit logging

Acceptance criteria:

- MCP plan works.
- MCP deploy fails without approval.
- MCP deploy works with approval token.
- MCP status/logs/stop work.
- CLI mirrors MCP flow.

Tests:

pnpm test:mcp
pnpm test:cli

Demo command:

crucible plan --prompt "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required."
crucible approve --plan-id <id>
crucible deploy --plan-id <id> --approval-token <token>
crucible status --deployment-id <id>
Phase 6 — Multi-provider planning

Goal: Show the neocloud vision even if only one live provider is enabled.

Build:

- provider score breakdown
- SkyPilot dry-run options if available
- provider capability matrix
- benchmark-history reliability score
- unavailable provider explanations

Dashboard should clearly distinguish:

Live deploy supported
Dry-run/planning supported
Configured but not tested
Unsupported

Acceptance criteria:

- User sees Lambda, Prime Intellect, CoreWeave, Modal capability status.
- App does not lie about support.
- Agent can explain why it chose the actual deploy path.
Phase 7 — Reliability hardening

Goal: Make it hold up under judge interaction.

Add error cases:

- unsupported model
- private HF model
- model likely too large
- unsupported provider
- provider unavailable
- missing approval
- failed endpoint health check
- stop while provisioning
- repeated deploy clicks
- user logs out mid-flow

Acceptance criteria:

- No crashes.
- Errors are human-readable.
- Agent gives next action.
- Logs are persisted.
- State machine remains valid.

Tests:

pnpm test:offscript
pnpm test:state-machine
pnpm test:e2e
Phase 8 — Demo polish

Goal: Make judges want to use it.

Build:

- polished landing page
- clean dashboard
- deployment timeline
- provider decision explanation
- Nia context panel
- endpoint card with curl and OpenAI SDK examples
- playground
- benchmark table
- MCP example panel
- stop button
- README demo script

Demo flow:

1. Open public URL.
2. Sign up as a new user.
3. Enter: “Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.”
4. Show agent plan.
5. Show Nia context used.
6. Show provider scoring.
7. Approve.
8. Deploy.
9. Watch logs.
10. Health check passes.
11. Test in playground.
12. Copy OpenAI-compatible endpoint.
13. Show MCP tool call from Hermes/OpenClaw-style agent.
14. Stop deployment.
11. Specific UI requirements

Keep the UI minimal.

Pages:

/
  landing page

/dashboard
  active deployments
  recent plans
  provider status
  quick new deployment

/deployments/new
  natural-language prompt
  advanced settings collapsed

/deployments/[id]
  status timeline
  endpoint
  logs
  health checks
  benchmark
  playground
  stop button

/providers
  capability matrix

/context
  Nia indexed sources
  recent context used

/agent
  MCP setup
  CLI setup
  API token

Avoid:

- giant settings screens
- fake analytics
- billing UI
- unnecessary charts
- complicated provider config UI

Use:

- Inter
- black/white/gray palette
- subtle borders
- Vercel-like spacing
- clear status badges
12. Revised non-negotiables for Codex
1. Public URL before final demo.
2. Real auth before final demo.
3. Real DB before final demo.
4. At least one real deployment path before final demo.
5. Nia must be visible in the product.
6. MCP must be available for external/personal agents.
7. Paid GPU launch requires approval.
8. Managed-account abuse guardrails required.
9. Stop/teardown required.
10. No fake provider support.
11. No localhost-only worker.
12. No secrets in logs.
13. No deployment marked ready before health checks pass.
14. If SkyPilot blocks, switch to Modal fallback.
15. Testing after every phase.
13. Best final product statement

Use this in README, landing page, and demo:

Crucible Compute is a hardware-agnostic deployment layer for open-source AI models.

It lets a user or agent request a model in natural language, then automatically profiles the model, compares GPU options, explains the best deployment target, asks for approval, launches a vLLM OpenAI-compatible endpoint, monitors health, and exposes the whole workflow through dashboard, CLI, and MCP.

One-line judge pitch:

Crucible gives every personal agent its own GPU deployment backend.
14. The tactical recommendation

For the hackathon, Codex should build in this exact order:

1. Public app + auth + DB.
2. Mock full deployment flow.
3. Nia-grounded agent planner.
4. Provider capability checker.
5. One real live deploy path.
6. Logs + health + stop.
7. MCP.
8. Multi-provider planning polish.
9. Demo polish.

The ideal outcome is SkyPilot live deploy. The acceptable winning outcome is Modal live deploy plus SkyPilot-backed provider planning. The unacceptable outcome is a beautiful dashboard with no auth, no real backend, no real deploy, or an agent that breaks when judges go off-script.
