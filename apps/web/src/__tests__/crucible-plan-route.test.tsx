import { describe, expect, it, vi } from "vitest";

describe("Crucible plan route memory", () => {
  it("uses only the current user's session memory when generating a plan", async () => {
    vi.resetModules();
    vi.stubEnv("CRUCIBLE_AUTH_STORE_PATH", `/tmp/crucible-auth-${Date.now()}-${Math.random()}.json`);
    vi.stubEnv("CRUCIBLE_MEMORY_STORE_PATH", `/tmp/crucible-memory-${Date.now()}-${Math.random()}.json`);
    vi.stubEnv("NIA_API_KEY", "");

    const { signup } = await import("../lib/server-auth");
    const { recordDeploymentMemory } = await import("../lib/deployment-memory");
    const { POST } = await import("../../app/api/crucible/plan/route");

    const current = await signup("current@example.com", "correct horse battery staple");
    const other = await signup("other@example.com", "correct horse battery staple");

    recordDeploymentMemory({
      userId: current.user.id,
      sessionId: current.session.token,
      prompt: "Deploy Qwen 7B cheaply",
      modelId: "Qwen/Qwen2.5-7B-Instruct",
      objective: "cheapest",
      provider: "Vast.ai",
      accelerator: "NVIDIA L4",
      estimatedHourlyUsd: 0.27,
      outcome: "failed",
      lesson: "Vast.ai L4 failed health checks; prefer Modal for this model next time."
    });
    recordDeploymentMemory({
      userId: other.user.id,
      sessionId: other.session.token,
      prompt: "Deploy private model",
      modelId: "private/model",
      objective: "reliable",
      provider: "CoreWeave",
      accelerator: "NVIDIA H100",
      estimatedHourlyUsd: 4.2,
      outcome: "ready",
      lesson: "Private model succeeded on CoreWeave."
    });

    const response = await POST(new Request("http://localhost/api/crucible/plan", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Cookie: `crucible_session=${current.session.token}`
      },
      body: JSON.stringify({
        prompt: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
        modelId: "Qwen/Qwen2.5-7B-Instruct",
        objective: "cheapest"
      })
    }));
    const body = await response.json();

    expect(body.recommendation.provider).toBe("Modal");
    expect(body.memoryInsights).toEqual([
      "Vast.ai L4 failed health checks; prefer Modal for this model next time."
    ]);
    expect(JSON.stringify(body)).not.toContain("private/model");
    vi.unstubAllEnvs();
  });
});
