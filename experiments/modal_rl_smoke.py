from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import modal
except ImportError:
    modal = None


APP_NAME = "nozomio-rl-gpu-smoke"
ARTIFACT_DIR = Path(".anygpu/rl_runs")

MODAL_PRICE_USD_PER_HOUR = {
    "T4": 0.59,
    "L4": 0.80,
    "A10G": 1.10,
}

if modal is not None:
    app = modal.App(APP_NAME)
    image = modal.Image.from_registry("pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime")
else:
    app = None
    image = None


@dataclass(frozen=True)
class TrainConfig:
    gpu_type: str = "T4"
    seed: int = 7
    n_envs: int = 4096
    rollout_steps: int = 64
    updates: int = 80
    ppo_epochs: int = 2
    minibatch_size: int = 8192
    env_size: int = 17
    max_episode_steps: int = 16
    learning_rate: float = 3e-4
    gamma: float = 0.98
    gae_lambda: float = 0.95
    clip_coef: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    eval_envs: int = 4096
    target_success_rate: float = 0.90
    min_success_delta: float = 0.25


def _as_config(**overrides: Any) -> TrainConfig:
    allowed = set(TrainConfig.__dataclass_fields__)
    clean = {key: value for key, value in overrides.items() if key in allowed and value is not None}
    return TrainConfig(**clean)


def _run_training(config_dict: dict[str, Any]) -> dict[str, Any]:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    config = _as_config(**config_dict)
    started = time.perf_counter()
    torch.manual_seed(config.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    gpu_name = torch.cuda.get_device_name(0) if device.type == "cuda" else None

    class VectorLineWorld:
        def __init__(self, n_envs: int) -> None:
            self.n_envs = n_envs
            self.pos = torch.zeros(n_envs, device=device, dtype=torch.long)
            self.steps = torch.zeros(n_envs, device=device, dtype=torch.long)

        def reset(self) -> torch.Tensor:
            self.pos.zero_()
            self.steps.zero_()
            return self.obs()

        def obs(self) -> torch.Tensor:
            return torch.stack(
                (
                    self.pos.float() / float(config.env_size - 1),
                    self.steps.float() / float(config.max_episode_steps),
                ),
                dim=-1,
            )

        def step(self, action: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            old_pos = self.pos
            delta = torch.where(action == 1, 1, -1)
            self.pos = (self.pos + delta).clamp(0, config.env_size - 1)
            self.steps += 1
            success = self.pos == config.env_size - 1
            timeout = self.steps >= config.max_episode_steps
            done = success | timeout
            progress = (self.pos - old_pos).float()
            reward = 0.02 * progress - 0.01
            reward = torch.where(success, torch.ones_like(reward), reward)
            if done.any():
                self.pos[done] = 0
                self.steps[done] = 0
            return self.obs(), reward, done.float()

    class ActorCritic(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.body = nn.Sequential(nn.Linear(2, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh())
            self.policy = nn.Linear(64, 2)
            self.value = nn.Linear(64, 1)

        def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
            hidden = self.body(obs)
            return self.policy(hidden), self.value(hidden).squeeze(-1)

        def act(self, obs: torch.Tensor, *, stochastic: bool) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
            logits, value = self(obs)
            dist = torch.distributions.Categorical(logits=logits)
            action = dist.sample() if stochastic else logits.argmax(dim=-1)
            return action, dist.log_prob(action), value

    def evaluate(model: ActorCritic, *, stochastic: bool) -> dict[str, float]:
        env = VectorLineWorld(config.eval_envs)
        obs = env.reset()
        active_return = torch.zeros(config.eval_envs, device=device)
        active_length = torch.zeros(config.eval_envs, device=device)
        returns: list[torch.Tensor] = []
        lengths: list[torch.Tensor] = []
        successes: list[torch.Tensor] = []
        while len(returns) < 4:
            with torch.no_grad():
                action, _, _ = model.act(obs, stochastic=stochastic)
            old_pos = env.pos.clone()
            obs, reward, done = env.step(action)
            active_return += reward
            active_length += 1
            if done.any():
                reached_goal = (old_pos + torch.where(action == 1, 1, -1)).clamp(0, config.env_size - 1) == config.env_size - 1
                returns.append(active_return[done.bool()].detach())
                lengths.append(active_length[done.bool()].detach())
                successes.append(reached_goal[done.bool()].float().detach())
                active_return[done.bool()] = 0
                active_length[done.bool()] = 0
        all_returns = torch.cat(returns)
        all_lengths = torch.cat(lengths)
        all_successes = torch.cat(successes)
        return {
            "mean_return": float(all_returns.mean().item()),
            "success_rate": float(all_successes.mean().item()),
            "mean_episode_length": float(all_lengths.mean().item()),
        }

    model = ActorCritic().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)

    baseline_random = 0.5 ** (config.env_size - 1)
    initial_eval = evaluate(model, stochastic=True)

    env = VectorLineWorld(config.n_envs)
    obs = env.reset()
    total_samples = 0
    last_loss = math.nan

    for _ in range(config.updates):
        obs_buf = []
        action_buf = []
        logprob_buf = []
        reward_buf = []
        done_buf = []
        value_buf = []

        for _step in range(config.rollout_steps):
            with torch.no_grad():
                action, logprob, value = model.act(obs, stochastic=True)
            next_obs, reward, done = env.step(action)
            obs_buf.append(obs)
            action_buf.append(action)
            logprob_buf.append(logprob)
            reward_buf.append(reward)
            done_buf.append(done)
            value_buf.append(value)
            obs = next_obs
            total_samples += config.n_envs

        with torch.no_grad():
            _, next_value = model(obs)

        rewards = torch.stack(reward_buf)
        dones = torch.stack(done_buf)
        values = torch.stack(value_buf)
        advantages = torch.zeros_like(rewards)
        lastgaelam = torch.zeros(config.n_envs, device=device)
        for step in reversed(range(config.rollout_steps)):
            next_nonterminal = 1.0 - dones[step]
            next_values = next_value if step == config.rollout_steps - 1 else values[step + 1]
            delta = rewards[step] + config.gamma * next_values * next_nonterminal - values[step]
            lastgaelam = delta + config.gamma * config.gae_lambda * next_nonterminal * lastgaelam
            advantages[step] = lastgaelam
        returns = advantages + values

        batch_obs = torch.cat(obs_buf)
        batch_actions = torch.cat(action_buf)
        batch_logprobs = torch.cat(logprob_buf)
        batch_advantages = advantages.reshape(-1)
        batch_returns = returns.reshape(-1)
        batch_values = values.reshape(-1)
        batch_advantages = (batch_advantages - batch_advantages.mean()) / (batch_advantages.std() + 1e-8)

        batch_size = batch_obs.shape[0]
        for _epoch in range(config.ppo_epochs):
            permutation = torch.randperm(batch_size, device=device)
            for start in range(0, batch_size, config.minibatch_size):
                idx = permutation[start : start + config.minibatch_size]
                logits, new_value = model(batch_obs[idx])
                dist = torch.distributions.Categorical(logits=logits)
                new_logprob = dist.log_prob(batch_actions[idx])
                entropy = dist.entropy().mean()
                ratio = (new_logprob - batch_logprobs[idx]).exp()
                pg_loss1 = -batch_advantages[idx] * ratio
                pg_loss2 = -batch_advantages[idx] * ratio.clamp(1 - config.clip_coef, 1 + config.clip_coef)
                policy_loss = torch.max(pg_loss1, pg_loss2).mean()
                value_loss = F.mse_loss(new_value, batch_returns[idx])
                loss = policy_loss + config.value_coef * value_loss - config.entropy_coef * entropy

                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 0.5)
                optimizer.step()
                last_loss = float(loss.detach().item())

        del batch_values

    trained_eval = evaluate(model, stochastic=False)
    duration_sec = time.perf_counter() - started
    hourly = MODAL_PRICE_USD_PER_HOUR.get(config.gpu_type)
    estimated_cost = None if hourly is None else hourly * duration_sec / 3600.0
    success_delta = trained_eval["success_rate"] - initial_eval["success_rate"]
    return_delta = trained_eval["mean_return"] - initial_eval["mean_return"]
    passed = (
        device.type == "cuda"
        and trained_eval["success_rate"] >= config.target_success_rate
        and success_delta >= config.min_success_delta
        and return_delta > 0
    )

    return {
        "passed": passed,
        "app_name": APP_NAME,
        "config": asdict(config),
        "device": str(device),
        "gpu_name": gpu_name,
        "samples": total_samples,
        "baseline_random_exact_success_probability": baseline_random,
        "initial_policy_eval": initial_eval,
        "trained_policy_eval": trained_eval,
        "improvement": {
            "success_rate_delta": success_delta,
            "mean_return_delta": return_delta,
        },
        "train": {
            "last_loss": last_loss,
            "duration_sec": duration_sec,
            "samples_per_second": total_samples / duration_sec,
        },
        "cost": {
            "price_source": "repo_static_modal_table",
            "estimated_gpu_usd_per_hour": hourly,
            "estimated_gpu_cost_usd": estimated_cost,
        },
    }


if app is not None:

    @app.function(image=image, gpu="T4", timeout=1200)
    def run_t4(config: dict[str, Any]) -> dict[str, Any]:
        config["gpu_type"] = "T4"
        return _run_training(config)

    @app.function(image=image, gpu="L4", timeout=1200)
    def run_l4(config: dict[str, Any]) -> dict[str, Any]:
        config["gpu_type"] = "L4"
        return _run_training(config)

    @app.function(image=image, gpu="A10G", timeout=1200)
    def run_a10g(config: dict[str, Any]) -> dict[str, Any]:
        config["gpu_type"] = "A10G"
        return _run_training(config)

    @app.local_entrypoint()
    def main(
        gpu: str = "T4",
        seed: int = 7,
        n_envs: int = 4096,
        rollout_steps: int = 64,
        updates: int = 80,
        ppo_epochs: int = 2,
        minibatch_size: int = 8192,
        target_success_rate: float = 0.90,
        min_success_delta: float = 0.25,
        output: str = "",
    ) -> None:
        config = asdict(
            _as_config(
                gpu_type=gpu,
                seed=seed,
                n_envs=n_envs,
                rollout_steps=rollout_steps,
                updates=updates,
                ppo_epochs=ppo_epochs,
                minibatch_size=minibatch_size,
                target_success_rate=target_success_rate,
                min_success_delta=min_success_delta,
            )
        )
        functions = {"T4": run_t4, "L4": run_l4, "A10G": run_a10g}
        if gpu not in functions:
            raise ValueError(f"Unsupported gpu {gpu!r}. Choose one of {', '.join(functions)}.")

        result = functions[gpu].remote(config)
        output_path = Path(output) if output else ARTIFACT_DIR / f"modal_rl_{gpu.lower()}_{int(time.time())}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, sort_keys=True))
        print(json.dumps(result, indent=2, sort_keys=True))
        print(f"artifact_path={output_path}")


def run_local_smoke(updates: int = 2, n_envs: int = 128, rollout_steps: int = 16) -> dict[str, Any]:
    return _run_training(
        asdict(
            _as_config(
                gpu_type="local",
                updates=updates,
                n_envs=n_envs,
                rollout_steps=rollout_steps,
                eval_envs=256,
                minibatch_size=1024,
                target_success_rate=0.0,
                min_success_delta=-1.0,
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the RL smoke experiment directly without Modal.")
    parser.add_argument("--gpu-type", default="direct")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--updates", type=int, default=2)
    parser.add_argument("--n-envs", type=int, default=128)
    parser.add_argument("--rollout-steps", type=int, default=16)
    parser.add_argument("--ppo-epochs", type=int, default=2)
    parser.add_argument("--minibatch-size", type=int, default=1024)
    parser.add_argument("--eval-envs", type=int, default=256)
    parser.add_argument("--target-success-rate", type=float, default=0.90)
    parser.add_argument("--min-success-delta", type=float, default=0.25)
    parser.add_argument("--output", default="")
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()
    result = _run_training(
        asdict(
            _as_config(
                gpu_type=args.gpu_type,
                seed=args.seed,
                updates=args.updates,
                n_envs=args.n_envs,
                rollout_steps=args.rollout_steps,
                ppo_epochs=args.ppo_epochs,
                minibatch_size=args.minibatch_size,
                eval_envs=args.eval_envs,
                target_success_rate=args.target_success_rate,
                min_success_delta=args.min_success_delta,
            )
        )
    )
    output = json.dumps(result, indent=2, sort_keys=True)
    print(output)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        print(f"artifact_path={output_path}")
    if args.require_cuda and result["device"] != "cuda":
        raise SystemExit("CUDA was required but the experiment did not run on CUDA.")
    if args.require_cuda and not result["passed"]:
        raise SystemExit("CUDA RL smoke did not meet the improvement gates.")
