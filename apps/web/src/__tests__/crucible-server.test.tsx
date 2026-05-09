import { describe, expect, it } from "vitest";

import { generateServerDeploymentPlan } from "../lib/crucible-server";

describe("generateServerDeploymentPlan", () => {
  it("keeps off-script latency requests inside the approval-gated planning contract", () => {
    const plan = generateServerDeploymentPlan({
      prompt: "Actually make it realtime, durable, and do not surprise me with GPU spend.",
      modelId: "Qwen/Qwen2.5-7B-Instruct"
    });

    expect(plan.status).toBe("generated");
    expect(plan.objective).toBe("reliable");
    expect(plan.approvalRequired).toBe(true);
    expect(plan.recommendation.reason).toContain("latency or reliability");
  });

  it("routes large model prompts to a larger GPU class without throwing", () => {
    const plan = generateServerDeploymentPlan({
      prompt: "Can you run a 70B model with multi GPU throughput?",
      modelId: "Qwen/Qwen2.5-72B-Instruct",
      objective: "balanced"
    });

    expect(plan.recommendation.provider).toBe("Vast.ai");
    expect(plan.recommendation.accelerator).toContain("H100");
    expect(plan.approvalRequired).toBe(true);
  });

  it("does not treat avoid multi-GPU wording as a large-GPU requirement", () => {
    const plan = generateServerDeploymentPlan({
      prompt: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
      modelId: "Qwen/Qwen2.5-7B-Instruct",
      objective: "cheapest"
    });

    expect(plan.recommendation.provider).toBe("Vast.ai");
    expect(plan.recommendation.accelerator).toBe("NVIDIA L4");
    expect(plan.recommendation.estimatedHourlyUsd).toBe(0.27);
  });

  it("uses past session memory to avoid repeating a failed provider choice", () => {
    const plan = generateServerDeploymentPlan({
      prompt: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
      modelId: "Qwen/Qwen2.5-7B-Instruct",
      objective: "cheapest",
      contextSnippets: [
        {
          id: "memory_failed_vast",
          source: "memory://session/failed-vast",
          title: "Past session memory",
          excerpt: "Previous Vast.ai L4 run for Qwen/Qwen2.5-7B-Instruct failed health checks; prefer Modal for the next attempt.",
          usedFor: "Avoid repeating failed deployment choices.",
          searchedAt: "2026-05-09T23:00:00.000Z"
        }
      ]
    });

    expect(plan.recommendation.provider).toBe("Modal");
    expect(plan.recommendation.reason).toContain("Past session memory");
  });
});
