import { describe, expect, it, vi } from "vitest";

describe("Crucible deploy route", () => {
  it("creates a deployment from a generated plan when a live gateway is configured", async () => {
    vi.resetModules();
    vi.stubEnv("CRUCIBLE_DEPLOYMENT_STORE_PATH", `/tmp/crucible-deployments-${Date.now()}-${Math.random()}.json`);
    vi.stubEnv("INSFORGE_API_BASE_URL", "");
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "https://gateway.example/v1");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200
    }));

    const { POST } = await import("../../app/api/crucible/deploy/route");
    const response = await POST(new Request("http://localhost/api/crucible/deploy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: {
          id: "plan_live",
          prompt: "Deploy Qwen 7B cheaply",
          modelId: "Qwen/Qwen2.5-7B-Instruct",
          objective: "cheapest",
          recommendation: {
            provider: "Vast.ai",
            accelerator: "NVIDIA L4",
            estimatedHourlyUsd: 0.27,
            reason: "The request fits a single economical L4-class GPU.",
            uncertainty: "Endpoint readiness depends on live provider capacity."
          },
          approvalRequired: true,
          approvalReason: "Deploy button is the explicit launch action.",
          status: "generated",
          createdAt: "2026-05-09T22:00:00.000Z"
        }
      })
    }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.deployment.id).toMatch(/^dep_/);
    expect(body.deployment.status).toBe("ready");
    expect(body.deployment.endpointUrl).toBe("https://gateway.example/v1");
    expect(body.deployment.provider).toBe("Vast.ai");
    expect(response.headers.getSetCookie().join("\n")).toContain("crucible_deployment_ids=");
    expect(response.headers.getSetCookie().join("\n")).toContain(`crucible_deployment_${body.deployment.id}=`);
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });
});
