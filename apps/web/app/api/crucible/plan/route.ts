import { NextResponse } from "next/server";

import { createBackendDeploymentPlan } from "@/lib/crucible-backend";
import {
  deploymentMemoryIdentity,
  deploymentMemoryInsights,
  deploymentMemorySnippets,
  listDeploymentMemory,
  recordDeploymentMemory
} from "@/lib/deployment-memory";
import { hasNiaApiKey, searchNia } from "@/lib/nia-server";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const identity = deploymentMemoryIdentity(request);
    const memory = listDeploymentMemory(identity.userId, identity.sessionId);
    const modelId = modelIdFromInput(body?.modelId);
    const objective = objectiveFromInput(body?.objective);
    const prompt = promptFromInput({
      prompt: body?.prompt,
      modelId,
      objective,
      notes: body?.notes
    });
    const contextSnippets = [
      ...deploymentMemorySnippets(memory),
      ...(await planNiaSnippets(prompt))
    ];
    const plan = await createBackendDeploymentPlan({
      userId: identity.userId,
      prompt,
      modelId,
      objective,
      sourceAgent: "web",
      contextSnippets
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

function promptFromInput(input: {
  prompt: unknown;
  modelId: string;
  objective?: string;
  notes: unknown;
}) {
  const existingPrompt = text(input.prompt);
  if (existingPrompt) {
    return existingPrompt;
  }
  const notes = text(input.notes);
  const objectiveLabel = input.objective ? objectiveLabels[input.objective] : "cheapest viable GPU";
  return notes
    ? `Deploy ${input.modelId} with ${objectiveLabel} objective. Notes: ${notes}`
    : `Deploy ${input.modelId} with ${objectiveLabel} objective.`;
}

function modelIdFromInput(value: unknown) {
  const raw = text(value);
  if (!raw) {
    return "Qwen/Qwen2.5-7B-Instruct";
  }
  try {
    const url = new URL(raw);
    if (url.hostname === "huggingface.co" || url.hostname.endsWith(".huggingface.co")) {
      const [owner, model] = url.pathname.split("/").filter(Boolean);
      if (owner && model) {
        return `${owner}/${model}`;
      }
    }
  } catch {
    // Plain Hugging Face model IDs are already valid input.
  }
  return raw.replace(/^huggingface\.co\//, "").replace(/^https?:\/\/huggingface\.co\//, "");
}

function objectiveFromInput(value: unknown) {
  const raw = text(value);
  return raw === "cheapest" || raw === "reliable" || raw === "low_latency"
    ? raw
    : undefined;
}

const objectiveLabels: Record<string, string> = {
  cheapest: "cheapest viable GPU",
  reliable: "most reliable",
  low_latency: "lowest latency"
};

async function planNiaSnippets(prompt: string) {
  if (!hasNiaApiKey()) {
    return [];
  }
  const response = await searchNia(`Crucible deployment plan provider GPU readiness: ${prompt}`);
  return response.snippets;
}

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}
