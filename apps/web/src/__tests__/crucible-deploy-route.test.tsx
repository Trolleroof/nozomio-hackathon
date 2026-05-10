import { describe, expect, it, vi } from "vitest";

describe("Crucible deploy route", () => {
  it("deploys a generated backend plan when the dashboard has no live gateway override", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_HOME", `/tmp/crucible-backend-${Date.now()}-${Math.random()}`);
    vi.stubEnv("CRUCIBLE_DEPLOYMENT_STORE_PATH", `/tmp/crucible-deployments-${Date.now()}-${Math.random()}.json`);
    vi.stubEnv("INSFORGE_API_BASE_URL", "");
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "");

    const { POST: planPost } = await import("../../app/api/crucible/plan/route");
    const planResponse = await planPost(new Request("http://localhost/api/crucible/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        modelId: "Qwen/Qwen2.5-7B-Instruct",
        objective: "cheapest"
      })
    }));
    const plan = await planResponse.json();

    const { POST } = await import("../../app/api/crucible/deploy/route");
    const response = await POST(new Request("http://localhost/api/crucible/deploy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan })
    }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.deployment.planId).toBe(plan.id);
    expect(body.deployment.status).toBe("ready");
    expect(body.deployment.endpointUrl).toContain("/v1/chat/completions");
    expect(body.deployment.logs.some((log: { message: string }) => log.message.includes("Health checks passed"))).toBe(true);
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("falls back to a serverless backend deployment when the Python bridge is unavailable", async () => {
    vi.resetModules();
    vi.stubEnv("CRUCIBLE_BACKEND_CWD", "/tmp/missing-crucible-backend");
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "");

    const { POST } = await import("../../app/api/crucible/deploy/route");
    const response = await POST(new Request("http://localhost/api/crucible/deploy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: {
          id: "plan_serverless",
          prompt: "Deploy Qwen 7B cheaply",
          modelId: "Qwen/Qwen2.5-7B-Instruct",
          objective: "cheapest",
          recommendation: {
            provider: "Modal",
            accelerator: "L4",
            estimatedHourlyUsd: 0,
            reason: "Use a single economical GPU.",
            uncertainty: "Serverless runtime will use the web fallback."
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
    expect(body.deployment.id).toMatch(/^deploy_/);
    expect(body.deployment.status).toBe("ready");
    expect(body.deployment.logs.some((log: { message: string }) => log.message.includes("serverless Crucible deployment"))).toBe(true);
    vi.unstubAllEnvs();
  });

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
