import { NextResponse } from "next/server";

import { generateServerDeploymentPlan } from "@/lib/crucible-server";
import {
  deploymentMemoryIdentity,
  deploymentMemoryInsights,
  deploymentMemorySnippets,
  listDeploymentMemory,
  recordDeploymentMemory
} from "@/lib/deployment-memory";
import { searchNia } from "@/lib/nia-server";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const identity = deploymentMemoryIdentity(request);
    const memory = listDeploymentMemory(identity.userId, identity.sessionId);
    const nia = await searchNiaForPlan(`${body?.prompt ?? ""} ${body?.modelId ?? ""}`.trim());
    const plan = generateServerDeploymentPlan({
      prompt: body?.prompt,
      modelId: body?.modelId,
      objective: body?.objective,
      stopPolicy: body?.stopPolicy,
      contextSnippets: [
        ...nia.snippets,
        ...deploymentMemorySnippets(memory)
      ]
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

function searchNiaForPlan(query: string) {
  return Promise.race([
    searchNia(query),
    new Promise<Awaited<ReturnType<typeof searchNia>>>((resolve) => {
      setTimeout(() => resolve({ connected: false, snippets: [] }), 12000);
    })
  ]);
}
