# InsForge RL/GPU Control Plane

This directory contains the InsForge/Postgres shape for making Crucible RL and GPU runs durable, queryable, and agent-safe.

The repo still works without live InsForge credentials. `anygpu.insforge_compute` mirrors the same concepts in the local SQLite `CrucibleStore` so tests and CLI/MCP workflows can run offline. The migration in `migrations/0001_rl_compute_control_plane.sql` is the portable schema for a real InsForge project.

## Feature Mapping

1. Run Capsules
   - Table: `rl_run_capsules`
   - Local API: `request_gpu_run`, `get_run_capsule`, `list_run_capsules`
   - Captures prompt, environment contract, provider offers, cost estimate, logs, metrics, artifacts, and audit result.

2. Agent Approval Ledger
   - Table: `rl_compute_approvals`
   - Local API: `approve_gpu_run`, `launch_gpu_run`
   - `launch_gpu_run` refuses to mark a paid run running unless the approval token resolves to a signed approval row for that run.

3. Live Compute Memory
   - Table: `rl_compute_memory`
   - Local API: `record_compute_memory`
   - Stores provider pricing, quota failures, GPU compatibility, and run outcomes for future agent planning.

4. Backend Branches for Experiments
   - Table: `rl_experiment_branches`
   - Local API: `create_experiment_branch`, `merge_experiment_branch`
   - Lets agents isolate schema/environment-contract experiments before merging them into the main control-plane surface.

5. Realtime Training Dashboard
   - Table: `rl_training_events`
   - Local API: `record_training_event`
   - Events use deterministic channels like `training:<run_id>` so a real InsForge realtime client can subscribe without a custom websocket service.

6. Agent-Native Schema Contracts
   - Table: `rl_environment_contracts`
   - Local API: `create_environment_contract`
   - Stores env spec, observation schema, action schema, reward spec, and pass criteria so agents can discover exactly what proves improvement.

7. Artifact Storage With Audit Metadata
   - Table: `rl_run_artifacts`
   - Local API: `publish_run_artifact`
   - Stores artifact URI plus searchable audit fields such as `passed`, `gpu_name`, `cost_usd`, `reward_delta`, and `success_rate_delta`.

8. Function-Based Safety Gates
   - Migration functions: `request_gpu_run`, `approve_run`, `mark_teardown_verified`, `publish_result`, `recommend_next_gpu_run`
   - Local API and MCP tools mirror these gates. Provider launch code should call the gate before any paid Modal/Vast/SkyPilot resource is created.

9. Ask the Backend What to Do Next
   - Function: `recommend_next_gpu_run`
   - Local API: `recommend_next_gpu_run`
   - Uses passing artifact metadata to recommend the cheapest verified next provider/GPU for an environment contract.

## Agent Tools

The Crucible MCP surface now exposes:

```text
crucible_create_experiment_branch
crucible_merge_experiment_branch
crucible_create_environment_contract
crucible_request_gpu_run
crucible_list_run_capsules
crucible_approve_gpu_run
crucible_launch_gpu_run
crucible_record_training_event
crucible_record_compute_memory
crucible_publish_run_artifact
crucible_recommend_next_gpu_run
```

These tools are intentionally policy-level. They create durable records and enforce approvals; they do not directly launch paid GPU infrastructure by themselves.
