import { describe, expect, it, vi } from "vitest";

import type { DeploymentPlan } from "@crucible/shared/crucible-contract";

const plan: DeploymentPlan = {
  id: "plan_demo_ready",
  prompt: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
  modelId: "Qwen/Qwen2.5-7B-Instruct",
  objective: "cheapest",
  recommendation: {
    provider: "Vast.ai",
    accelerator: "NVIDIA L4",
    estimatedHourlyUsd: 0.27,
    reason: "A single L4 is the cheapest viable route for the demo model.",
    uncertainty: "Live capacity may change before launch."
  },
  approvalRequired: true,
  approvalReason: "Approval required before launching paid GPU resources from a personal agent.",
  status: "generated",
  createdAt: "2026-05-09T22:00:00.000Z"
};

describe("Crucible deployments", () => {
  it("refuses to create a deployment when no external gateway is configured", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "");
    vi.stubEnv("INSFORGE_API_BASE_URL", "");
    vi.stubEnv("CRUCIBLE_DEPLOYMENT_STORE_PATH", `/tmp/crucible-deployments-${Date.now()}-${Math.random()}.json`);

    const { deployPlan, getStoredDeployment } = await import("../lib/crucible-deployments");

    await expect(deployPlan(plan)).rejects.toThrow("No live AnyGPU gateway is configured");
    await expect(getStoredDeployment("missing")).resolves.toBeNull();
    vi.unstubAllEnvs();
  });

  it("creates a stored deployment only from a verified live gateway", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "https://gateway.example/v1");
    vi.stubEnv("INSFORGE_API_BASE_URL", "");
    vi.stubEnv("CRUCIBLE_DEPLOYMENT_STORE_PATH", `/tmp/crucible-deployments-${Date.now()}-${Math.random()}.json`);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200
    }));

    const { deployPlan, getStoredDeployment } = await import("../lib/crucible-deployments");
    const deployment = await deployPlan(plan);

    expect(fetch).toHaveBeenCalledWith("https://gateway.example/v1/models", expect.objectContaining({ cache: "no-store" }));
    expect(deployment.status).toBe("ready");
    expect(deployment.endpointUrl).toBe("https://gateway.example/v1");
    expect(deployment.logs.map((log) => log.message).join("\n")).toContain("AnyGPU gateway");
    await expect(getStoredDeployment(deployment.id)).resolves.toEqual(deployment);
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("stops a stored deployment and records the control-plane event", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "https://gateway.example/v1");
    vi.stubEnv("INSFORGE_API_BASE_URL", "");
    vi.stubEnv("CRUCIBLE_DEPLOYMENT_STORE_PATH", `/tmp/crucible-deployments-${Date.now()}-${Math.random()}.json`);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200
    }));

    const { deployPlan, getStoredDeployment, stopStoredDeployment } = await import("../lib/crucible-deployments");
    const deployment = await deployPlan(plan);

    const stopped = stopStoredDeployment(deployment.id);

    expect(stopped.status).toBe("stopped");
    expect(stopped.logs.at(0)?.message).toContain("Stop requested");
    await expect(getStoredDeployment(deployment.id)).resolves.toEqual(expect.objectContaining({ status: "stopped" }));
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });
});
