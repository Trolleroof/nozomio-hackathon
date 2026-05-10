import "@testing-library/jest-dom";
import { afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ContextPage from "../../app/context/page";
import DashboardPage from "../../app/dashboard/page";
import DeploymentDetailPage from "../../app/deployments/[id]/page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({
    refresh: vi.fn()
  })
}));

describe("DashboardPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("shows the protected operational dashboard content without fixture deployments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("gateway unavailable")));
    render(await DashboardPage());
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("Active deployments")).toBeInTheDocument();
    expect(screen.getByText("No live deployments found. Start the AnyGPU gateway or deploy a real model to populate this list.")).toBeInTheDocument();
    expect(screen.getByText("Provider status")).toBeInTheDocument();
    expect(screen.getByText("Endpoint")).toBeInTheDocument();
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(screen.getByText("base_url")).toBeInTheDocument();
  });

  it("shows RL and training runs on the operational dashboard", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("gateway unavailable")));
    vi.stubEnv("CRUCIBLE_TRAINING_RUNS_JSON", JSON.stringify([
      {
        id: "run_ppo_t4",
        name: "line_world_ppo",
        kind: "rl",
        status: "running",
        phase: "train",
        provider: "Modal",
        gpuName: "Tesla T4",
        rewardMean: 1.2,
        successRate: 1,
        rolloutCount: 3,
        costBurnUsd: 0.00065,
        updatedAt: "2026-05-09T22:00:00Z",
        latestEvent: "PPO update 3 passed target success rate."
      },
      {
        id: "run_sft_l4",
        name: "support_sft",
        kind: "training",
        status: "approval_required",
        phase: "queued",
        provider: "Vast.ai",
        gpuName: "L4",
        rewardMean: null,
        successRate: null,
        rolloutCount: null,
        costBurnUsd: 0.03,
        updatedAt: "2026-05-09T21:30:00Z",
        latestEvent: "Waiting for signed approval before launch."
      }
    ]));

    render(await DashboardPage());

    expect(screen.getByText("RL and training runs")).toBeInTheDocument();
    expect(screen.getByText("1 running")).toBeInTheDocument();
    expect(screen.getAllByText("line_world_ppo").length).toBeGreaterThan(0);
    expect(screen.getAllByText("support_sft").length).toBeGreaterThan(0);
    expect(screen.getByText("Modal / Tesla T4")).toBeInTheDocument();
    expect(screen.getByText("success 100%")).toBeInTheDocument();
    expect(screen.getByText("reward 1.20")).toBeInTheDocument();
    expect(screen.getByText("3 rollouts")).toBeInTheDocument();
    expect(screen.getByText("cost $0.0007")).toBeInTheDocument();
    expect(screen.getByText("PPO update 3 passed target success rate.")).toBeInTheDocument();
  });

  it("includes test runs in deployment history", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("gateway unavailable")));
    vi.stubEnv("CRUCIBLE_TRAINING_RUNS_JSON", JSON.stringify([
      {
        id: "run_smoke_qwen",
        name: "qwen_smoke_eval",
        kind: "benchmark",
        status: "passed",
        phase: "smoke",
        provider: "Modal",
        gpuName: "L4",
        updatedAt: "2026-05-09T23:00:00Z",
        latestEvent: "Smoke eval passed before promotion."
      }
    ]));

    render(await DashboardPage());

    expect(screen.getByText("Deployment history")).toBeInTheDocument();
    expect(screen.getByText("1 events")).toBeInTheDocument();
    expect(screen.getAllByText("qwen_smoke_eval").length).toBeGreaterThan(0);
    expect(screen.getByText("Test run · Modal / L4 · smoke")).toBeInTheDocument();
    expect(screen.getAllByText("Passed").length).toBeGreaterThan(0);
  });
});

describe("DeploymentDetailPage", () => {
  it("shows a missing deployment state instead of falling back to a fixture", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: [] })
    }));

    render(await DeploymentDetailPage({ params: Promise.resolve({ id: "dep_qwen_modal" }) }));
    expect(screen.getByRole("heading", { name: "Deployment not found" })).toBeInTheDocument();
    expect(screen.getByText("No real deployment exists for dep_qwen_modal.")).toBeInTheDocument();
    expect(screen.queryByText("Qwen safe Modal demo")).not.toBeInTheDocument();
  });

  it("shows the deployment operations surface for a real gateway model", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        data: [
          {
            id: "live-chat",
            anygpu: {
              health: "healthy",
              provider: "docker",
              runtime: "vllm",
              simulated: false,
              upstream_url: "http://127.0.0.1:8080"
            }
          }
        ]
      })
    }));

    render(await DeploymentDetailPage({ params: Promise.resolve({ id: "live-chat" }) }));
    expect(screen.getByText("Endpoint")).toBeInTheDocument();
    expect(screen.getByText("Health checks")).toBeInTheDocument();
    expect(screen.getByText("Logs")).toBeInTheDocument();
    expect(screen.getByText("Benchmark")).toBeInTheDocument();
    expect(screen.getByText("Playground")).toBeInTheDocument();
    expect(screen.getByText("Stop deployment")).toBeInTheDocument();
  });
});

describe("ContextPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("does not show cached fixture context when Nia is not configured", async () => {
    vi.stubEnv("NIA_API_KEY", "");
    render(await ContextPage());
    expect(screen.getByText("Evidence hits")).toBeInTheDocument();
    expect(screen.getByText("Source coverage")).toBeInTheDocument();
    expect(screen.getByText("Recent Nia decision checks")).toBeInTheDocument();
    expect(screen.getByText("Context snippets used in agent decisions")).toBeInTheDocument();
    expect(screen.getByText("No context snippets yet. Configure NIA_API_KEY or run a search to populate live context.")).toBeInTheDocument();
    expect(screen.queryByText("SkyPilot docs")).not.toBeInTheDocument();
  });
});
