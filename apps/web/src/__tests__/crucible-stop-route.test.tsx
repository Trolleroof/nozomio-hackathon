import { describe, expect, it, vi } from "vitest";

import type { DeploymentPlan } from "@crucible/shared/crucible-contract";

const plan: DeploymentPlan = {
  id: "plan_stop_route",
  prompt: "Deploy Qwen 7B cheaply.",
  modelId: "Qwen/Qwen2.5-7B-Instruct",
  objective: "cheapest",
  recommendation: {
    provider: "Vast.ai",
    accelerator: "NVIDIA L4",
    estimatedHourlyUsd: 0.27,
    reason: "A single L4 is enough for the demo.",
    uncertainty: "Capacity can change."
  },
  approvalRequired: true,
  approvalReason: "Deploy button is the explicit launch action.",
  status: "generated",
  createdAt: "2026-05-09T22:00:00.000Z"
};

describe("Crucible stop route", () => {
  it("stops a stored deployment by id", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "");
    vi.stubEnv("INSFORGE_API_BASE_URL", "");
    vi.stubEnv("CRUCIBLE_DEPLOYMENT_STORE_PATH", `/tmp/crucible-deployments-${Date.now()}-${Math.random()}.json`);

    const { deployPlan } = await import("../lib/crucible-deployments");
    const { POST } = await import("../../app/api/crucible/deployments/[id]/stop/route");
    const deployment = await deployPlan(plan);

    const response = await POST(new Request(`http://localhost/api/crucible/deployments/${deployment.id}/stop`, {
      method: "POST"
    }), {
      params: Promise.resolve({ id: deployment.id })
    });
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.deployment.status).toBe("stopped");
    vi.unstubAllEnvs();
  });
});
