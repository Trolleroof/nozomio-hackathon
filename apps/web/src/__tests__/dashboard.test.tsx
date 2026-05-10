import "@testing-library/jest-dom";
import { spawnSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
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

  it("shows Hermes-triggered MCP run capsules from the Crucible backend", async () => {
    const home = mkdtempSync(`${tmpdir()}/crucible-dashboard-mcp-`);
    vi.stubEnv("ANYGPU_HOME", home);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("gateway unavailable")));

    const admin = runPythonJson(["-m", "anygpu", "crucible", "signup", "--email", "hermes@example.com", "--password", "pw", "--role", "admin"], home);
    const contract = bridgeMcpCall(home, "crucible_create_environment_contract", {
      name: "cartpole_ppo",
      envSpec: { runtime: "gymnasium", max_steps: 128 },
      observationSchema: { shape: [4], dtype: "float32" },
      actionSchema: { type: "discrete", n: 2 },
      rewardSpec: { target: "episode_return" },
      passCriteria: { min_success_rate: 0.9 }
    }).content;
    const capsule = bridgeMcpCall(home, "crucible_request_gpu_run", {
      userId: admin.id,
      prompt: "Train CartPole through Hermes",
      envContractId: contract.id,
      providerOffers: [{ provider: "modal", gpu_name: "Tesla T4", price_per_hr: 0.59, available: true }],
      costEstimate: { estimated_cost_usd: 0.02 },
      sourceAgent: "hermes"
    }).content;
    const approval = bridgeMcpCall(home, "crucible_approve_gpu_run", {
      runId: capsule.id,
      approvedBy: admin.id,
      provider: "modal",
      budgetUsd: 0.05,
      maxRuntimeMinutes: 15,
      teardownPolicy: { terminate: "always" }
    }).content;
    bridgeMcpCall(home, "crucible_launch_gpu_run", { runId: capsule.id, approvalToken: approval.token });
    bridgeMcpCall(home, "crucible_record_training_event", {
      runId: capsule.id,
      phase: "train",
      rolloutCount: 12,
      rewardMean: 188,
      successRate: 0.92,
      costBurnUsd: 0.008,
      gpuName: "Tesla T4",
      message: "Hermes wrapper recorded PPO progress."
    });

    render(await DashboardPage());

    expect(screen.getByText("RL and training runs")).toBeInTheDocument();
    expect(screen.getByText("Train CartPole through Hermes")).toBeInTheDocument();
    expect(screen.getByText("hermes · train · Tesla T4")).toBeInTheDocument();
    expect(screen.getByText("92% success")).toBeInTheDocument();
    expect(screen.getByText("1 running")).toBeInTheDocument();
  });
});

function bridgeMcpCall(home: string, toolName: string, args: Record<string, unknown>) {
  const response = runPythonJson(
    ["-m", "anygpu.crucible_web_bridge"],
    home,
    JSON.stringify({ action: "mcp_call", toolName, arguments: args })
  );
  expect(response.isError).toBe(false);
  return response;
}

function runPythonJson(args: string[], home: string, input?: string) {
  const root = resolve(process.cwd(), "..", "..");
  const result = spawnSync(process.env.PYTHON || "python3", args, {
    cwd: root,
    env: {
      ...process.env,
      ANYGPU_HOME: home,
      PYTHONPATH: root
    },
    input,
    encoding: "utf8"
  });
  expect(result.status, result.stderr || result.stdout).toBe(0);
  return JSON.parse(result.stdout);
}

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
