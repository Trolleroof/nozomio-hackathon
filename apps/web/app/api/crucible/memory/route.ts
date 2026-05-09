import { NextResponse } from "next/server";

import {
  deploymentMemoryIdentity,
  recordDeploymentMemory
} from "@/lib/deployment-memory";
import type { DeploymentObjective } from "@crucible/shared/crucible-contract";

const outcomes = new Set(["planned", "ready", "failed", "stopped"]);

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const plan = body?.plan;
    const recommendation = plan?.recommendation;
    const outcome = typeof body?.outcome === "string" && outcomes.has(body.outcome)
      ? body.outcome
      : "planned";
    const identity = deploymentMemoryIdentity(request);
    const entry = recordDeploymentMemory({
      ...identity,
      prompt: text(plan?.prompt, "Deployment run"),
      modelId: text(plan?.modelId, "unknown-model"),
      objective: objective(plan?.objective),
      provider: text(recommendation?.provider, "Unknown provider"),
      accelerator: text(recommendation?.accelerator, "Unknown accelerator"),
      estimatedHourlyUsd: number(recommendation?.estimatedHourlyUsd),
      outcome,
      lesson: text(body?.lesson, "")
    });

    return NextResponse.json({
      memoryInsights: [entry.lesson]
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Memory update failed." },
      { status: 400 }
    );
  }
}

function text(value: unknown, fallback: string) {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function number(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function objective(value: unknown): DeploymentObjective {
  return value === "cheapest" || value === "reliable" || value === "low_latency" || value === "balanced"
    ? value
    : "balanced";
}
