import { describe, expect, it, vi } from "vitest";

describe("Crucible memory route", () => {
  it("records a deployment outcome for the current user session", async () => {
    vi.resetModules();
    vi.stubEnv("CRUCIBLE_AUTH_STORE_PATH", `/tmp/crucible-auth-${Date.now()}-${Math.random()}.json`);
    vi.stubEnv("CRUCIBLE_MEMORY_STORE_PATH", `/tmp/crucible-memory-${Date.now()}-${Math.random()}.json`);

    const { signup } = await import("../lib/server-auth");
    const { listDeploymentMemory } = await import("../lib/deployment-memory");
    const { POST } = await import("../../app/api/crucible/memory/route");
    const current = await signup("current@example.com", "correct horse battery staple");

    const response = await POST(new Request("http://localhost/api/crucible/memory", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Cookie: `crucible_session=${current.session.token}`
      },
      body: JSON.stringify({
        outcome: "failed",
        lesson: "Modal cold start missed the demo window; warm it before judge traffic.",
        plan: {
          prompt: "Deploy Qwen 7B for a judge demo.",
          modelId: "Qwen/Qwen2.5-7B-Instruct",
          objective: "low_latency",
          recommendation: {
            provider: "Modal",
            accelerator: "NVIDIA L4",
            estimatedHourlyUsd: 0.8
          }
        }
      })
    }));
    const body = await response.json();
    const memory = listDeploymentMemory(current.user.id, current.session.token);

    expect(response.status).toBe(200);
    expect(body.memoryInsights).toEqual([
      "Modal cold start missed the demo window; warm it before judge traffic."
    ]);
    expect(memory[0]).toEqual(expect.objectContaining({
      outcome: "failed",
      provider: "Modal",
      lesson: "Modal cold start missed the demo window; warm it before judge traffic."
    }));
    vi.unstubAllEnvs();
  });
});
