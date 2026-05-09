import type {
  DeploymentObjective,
  DeploymentPlan,
  NiaContextSnippet
} from "@crucible/shared/crucible-contract";
import { generatedPlan } from "@crucible/shared/fixtures";

export interface GenerateDeploymentPlanInput {
  prompt: string;
  modelId: string;
  objective?: DeploymentObjective;
  stopPolicy?: string;
  contextSnippets?: NiaContextSnippet[];
}

export function generateServerDeploymentPlan(input: GenerateDeploymentPlanInput): DeploymentPlan {
  const prompt = cleanText(input.prompt) || generatedPlan.prompt;
  const modelId = cleanText(input.modelId) || generatedPlan.modelId;
  const objective = input.objective ?? inferObjective(prompt);
  const recommendation = applyNiaContext(
    recommendPlacement({ prompt, modelId, objective }),
    input.contextSnippets
  );

  return {
    ...generatedPlan,
    id: `plan_${hashStable(`${prompt}:${modelId}:${objective}`).slice(0, 12)}`,
    prompt,
    modelId,
    objective,
    recommendation,
    approvalRequired: true,
    approvalReason: approvalReason(input.stopPolicy),
    status: "generated",
    createdAt: new Date().toISOString()
  };
}

function recommendPlacement({
  prompt,
  modelId,
  objective
}: {
  prompt: string;
  modelId: string;
  objective: DeploymentObjective;
}): DeploymentPlan["recommendation"] {
  const lowered = `${prompt} ${modelId}`.toLowerCase();
  const avoidsMultiGpu = /\b(avoid|no|without|unless required)\b.{0,24}\bmulti[- ]?gpu\b/.test(lowered);
  const isLarge =
    /\b(32b|70b|72b|moe|high[- ]?throughput)\b/.test(lowered) ||
    (/\bmulti[- ]?gpu\b/.test(lowered) && !avoidsMultiGpu);
  const wantsLatency = objective === "low_latency" || /\b(low latency|fast|realtime|real-time|p95)\b/.test(lowered);
  const wantsReliability = objective === "reliable" || /\b(reliable|fallback|production|uptime|redundan|durable)\b/.test(lowered);

  if (isLarge) {
    return {
      provider: "Vast.ai",
      accelerator: "NVIDIA A100 or H100",
      estimatedHourlyUsd: 1.1,
      reason: "The request appears to need a larger GPU class; marketplace capacity is checked before any paid launch.",
      uncertainty: "Exact capacity, quota, exposed ports, and model boot health must be verified after approval."
    };
  }

  if (wantsLatency || wantsReliability) {
    return {
      provider: "Modal",
      accelerator: "NVIDIA L4",
      estimatedHourlyUsd: 0.8,
      reason: "The request prioritizes latency or reliability, so the plan favors the managed OpenAI-compatible path.",
      uncertainty: "Cold-start and p95 latency still require a live health check before traffic is routed."
    };
  }

  return {
    provider: "Vast.ai",
    accelerator: "NVIDIA L4",
    estimatedHourlyUsd: 0.27,
    reason: "The request fits a single economical L4-class GPU and keeps paid launch behind explicit approval.",
    uncertainty: "Final memory fit, exact hourly price, and endpoint readiness depend on live provider capacity."
  };
}

function inferObjective(prompt: string): DeploymentObjective {
  const lowered = prompt.toLowerCase();
  if (/\b(cheap|cheapest|budget|cost)\b/.test(lowered)) {
    return "cheapest";
  }
  if (/\b(reliable|fallback|uptime|production|durable)\b/.test(lowered)) {
    return "reliable";
  }
  if (/\b(latency|fast|realtime|real-time|p95)\b/.test(lowered)) {
    return "low_latency";
  }
  return "balanced";
}

function approvalReason(stopPolicy?: string) {
  if (stopPolicy && stopPolicy !== "manual") {
    return `Approval required before launching paid GPU resources; teardown policy is ${stopPolicy}.`;
  }
  return "Approval required before launching paid GPU resources from a personal agent.";
}

function cleanText(value: unknown) {
  return typeof value === "string" ? value.trim().replace(/\s+/g, " ") : "";
}

function applyNiaContext(
  recommendation: DeploymentPlan["recommendation"],
  snippets: NiaContextSnippet[] | undefined
): DeploymentPlan["recommendation"] {
  const relevant = (snippets ?? [])
    .filter((snippet) => snippet.title || snippet.source)
    .slice(0, 2)
    .map((snippet) => snippet.title || snippet.source);
  if (relevant.length === 0) {
    return recommendation;
  }
  const memoryOverride = memoryPlacementOverride(snippets ?? []);
  if (memoryOverride) {
    return {
      ...recommendation,
      ...memoryOverride,
      reason: `Past session memory changed this recommendation: ${memoryOverride.reason} NIA context consulted: ${relevant.join("; ")}.`,
      uncertainty: `${recommendation.uncertainty} Past session memory is user-scoped and should be checked against live provider readiness before launch.`
    };
  }
  return {
    ...recommendation,
    reason: `${recommendation.reason} NIA context consulted: ${relevant.join("; ")}.`,
    uncertainty: `${recommendation.uncertainty} NIA context can change, so provider readiness is rechecked at launch time.`
  };
}

function memoryPlacementOverride(snippets: NiaContextSnippet[]) {
  const memoryText = snippets
    .filter((snippet) => snippet.source.startsWith("memory://"))
    .map((snippet) => `${snippet.title} ${snippet.excerpt}`.toLowerCase())
    .join(" ");
  if (!memoryText) {
    return null;
  }
  if (memoryText.includes("vast.ai") && memoryText.includes("failed") && memoryText.includes("prefer modal")) {
    return {
      provider: "Modal",
      accelerator: "NVIDIA L4",
      estimatedHourlyUsd: 0.8,
      reason: "a previous Vast.ai attempt failed health checks and the recorded lesson says to prefer Modal for the retry."
    };
  }
  return null;
}

function hashStable(value: string) {
  let hash = 5381;
  for (const char of value) {
    hash = ((hash << 5) + hash) ^ char.charCodeAt(0);
  }
  return Math.abs(hash).toString(36);
}
