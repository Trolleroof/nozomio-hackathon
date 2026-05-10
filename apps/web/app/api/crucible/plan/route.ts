import { NextResponse } from "next/server";

import { createBackendDeploymentPlan } from "@/lib/crucible-backend";
import {
  deploymentMemoryIdentity,
  deploymentMemoryInsights,
  listDeploymentMemory,
  recordDeploymentMemory
} from "@/lib/deployment-memory";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const identity = deploymentMemoryIdentity(request);
    const memory = listDeploymentMemory(identity.userId, identity.sessionId);
    const plan = await createBackendDeploymentPlan({
      userId: identity.userId,
      prompt: body?.prompt,
      modelId: body?.modelId,
      objective: body?.objective,
      sourceAgent: "web"
    });
    const memoryInsights = deploymentMemoryInsights(memory);
    recordDeploymentMemory({
      ...identity,
      prompt: plan.prompt,
      modelId: plan.modelId,
      objective: plan.objective,
      provider: plan.recommendation.provider,
      accelerator: plan.recommendation.accelerator,
      estimatedHourlyUsd: plan.recommendation.estimatedHourlyUsd,
      outcome: "planned",
      lesson: `${plan.recommendation.provider} ${plan.recommendation.accelerator} was planned for ${plan.modelId}; ${plan.recommendation.reason}`
    });
    return NextResponse.json({
      ...plan,
      memoryInsights
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Plan generation failed." },
      { status: 400 }
    );
  }
}
