import { describe, expect, it, vi } from "vitest";

describe("deployment memory store", () => {
  it("keeps deployment run memory scoped to the current user session", async () => {
    vi.resetModules();
    vi.stubEnv("CRUCIBLE_MEMORY_STORE_PATH", `/tmp/crucible-memory-${Date.now()}-${Math.random()}.json`);
    const {
      listDeploymentMemory,
      recordDeploymentMemory
    } = await import("../lib/deployment-memory");

    recordDeploymentMemory({
      userId: "user_a",
      sessionId: "session_a",
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
      userId: "user_b",
      sessionId: "session_b",
      prompt: "Deploy private model",
      modelId: "private/model",
      objective: "reliable",
      provider: "CoreWeave",
      accelerator: "NVIDIA H100",
      estimatedHourlyUsd: 4.2,
      outcome: "ready",
      lesson: "Private account quota was healthy."
    });

    const currentSession = listDeploymentMemory("user_a", "session_a");

    expect(currentSession).toHaveLength(1);
    expect(currentSession[0]).toEqual(expect.objectContaining({
      modelId: "Qwen/Qwen2.5-7B-Instruct",
      provider: "Vast.ai",
      outcome: "failed"
    }));
    expect(JSON.stringify(currentSession)).not.toContain("private/model");
    vi.unstubAllEnvs();
  });
});
