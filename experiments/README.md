# Nozomio RL GPU Smoke

This folder contains a cheap RL smoke test for proving that a model can improve on a GPU-backed environment before wiring a larger benchmark.

The environment is a Torch-vectorized line world. A random/untrained policy starts at 0% success; the PPO-style actor-critic should reach at least 90% success. GPU completion requires the artifact to report `device: "cuda"` and pass `experiments/audit_rl_result.py`.

## Local CPU Check

```bash
python experiments/modal_rl_smoke.py \
  --gpu-type local \
  --updates 3 \
  --n-envs 128 \
  --rollout-steps 16 \
  --ppo-epochs 2 \
  --minibatch-size 1024 \
  --eval-envs 256 \
  --output .anygpu/rl_runs/local_direct_smoke.json

python experiments/audit_rl_result.py .anygpu/rl_runs/local_direct_smoke.json --allow-cpu
```

Check whether the overall GPU objective is complete:

```bash
python experiments/rl_run_status.py
```

This exits non-zero until at least one artifact passes the CUDA/GPU completion audit.

## Read-Only Provider Price Check

This loads the ignored repo-local `.env`, calls provider price/availability APIs, and writes a local summary. It does not launch resources.

```bash
set -a
source .env
set +a
python experiments/provider_price_check.py --output .anygpu/rl_runs/provider_price_check.json
```

## Modal T4 Check

This uploads `experiments/modal_rl_smoke.py` to Modal and may incur GPU spend.

```bash
modal run experiments/modal_rl_smoke.py \
  --gpu T4 \
  --updates 3 \
  --n-envs 4096 \
  --rollout-steps 16 \
  --ppo-epochs 2 \
  --minibatch-size 8192 \
  --target-success-rate 0.90 \
  --min-success-delta 0.25 \
  --output .anygpu/rl_runs/modal_rl_t4_run.json

python experiments/audit_rl_result.py .anygpu/rl_runs/modal_rl_t4_run.json
```

## SkyPilot AWS T4 Spot Check

This launches paid AWS infrastructure through the local SkyPilot API server. It uses a T4 spot request to keep cost low and fails if CUDA is unavailable or the policy does not improve.

```bash
sky launch -y experiments/skypilot_rl_smoke.yaml
sky down -y nozomio-rl-gpu-smoke
```

The remote job writes `.anygpu/rl_runs/skypilot_rl_t4_run.json` inside the SkyPilot workdir and audits it in-place.
