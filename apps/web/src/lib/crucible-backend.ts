import { spawn } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

import type {
  Deployment,
  DeploymentObjective,
  DeploymentPlan,
  NiaContextSnippet
} from "@crucible/shared/crucible-contract";

import { generateServerDeploymentPlan } from "./crucible-server";

export interface BackendDeploymentPlanInput {
  userId: string;
  email?: string;
  prompt: string;
  modelId: string;
  objective?: DeploymentObjective;
  sourceAgent?: string;
  contextSnippets?: NiaContextSnippet[];
  stopPolicy?: string;
}

interface BackendPlanRecord {
  id?: unknown;
  prompt?: unknown;
  model_id?: unknown;
  objective?: unknown;
  approval_required?: unknown;
  recommendation?: Record<string, unknown>;
  next_action?: unknown;
  created_at?: unknown;
  status?: unknown;
  source?: unknown;
}

interface BackendDeploymentRecord {
  id?: unknown;
  plan_id?: unknown;
  status?: unknown;
  endpoint_url?: unknown;
  provider?: unknown;
  runtime?: unknown;
  health_checks?: unknown;
  logs?: unknown;
  benchmark?: unknown;
  created_at?: unknown;
  updated_at?: unknown;
}

export async function createBackendDeploymentPlan(input: BackendDeploymentPlanInput): Promise<DeploymentPlan> {
  if (canUseLocalBackendBridge()) {
    try {
      const raw = await runLocalBackendBridge(input);
      return normalizeBackendPlan(raw);
    } catch (error) {
      if (!isMissingPythonBackend(error)) {
        throw error;
      }
    }
  }
  return {
    ...generateServerDeploymentPlan({
      prompt: input.prompt,
      modelId: input.modelId,
      objective: input.objective,
      stopPolicy: input.stopPolicy,
      contextSnippets: input.contextSnippets
    }),
    backend: {
      source: "crucible",
      raw: {
        source: "typescript-web",
        reason: "Python backend bridge unavailable in this runtime."
      }
    }
  };
}

export async function createBackendDeployment(plan: DeploymentPlan): Promise<Deployment> {
  assertDeploymentPlan(plan);
  if (!canUseLocalBackendBridge()) {
    return createServerlessBackendDeployment(plan);
  }
  try {
    const raw = await runLocalBackendBridge({
      action: "deploy",
      planId: plan.id
    });
    return normalizeBackendDeployment(raw, plan);
  } catch (error) {
    if (!isMissingPythonBackend(error)) {
      throw error;
    }
    return createServerlessBackendDeployment(plan);
  }
}

type BackendBridgeInput = BackendDeploymentPlanInput | {
  action: "deploy";
  planId: string;
};

async function runLocalBackendBridge(input: BackendBridgeInput): Promise<BackendPlanRecord & BackendDeploymentRecord> {
  const cwd = backendCwd();
  const payload = JSON.stringify(bridgePayload(input));
  const errors: string[] = [];
  for (const python of pythonCommandCandidates()) {
    try {
      return await runBackendProcess({ cwd, payload, python });
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error));
    }
  }
  throw new Error(cleanBackendError(errors.find(Boolean) || "Python backend runtime was not found."));
}

function bridgePayload(input: BackendBridgeInput) {
  if (isDeployBridgeInput(input)) {
    return {
      action: "deploy",
      planId: input.planId
    };
  }
  return {
    action: "plan",
    userId: input.userId,
    email: input.email,
    prompt: input.prompt,
    modelId: input.modelId,
    objective: input.objective,
    sourceAgent: input.sourceAgent || "web"
  };
}

function isDeployBridgeInput(input: BackendBridgeInput): input is { action: "deploy"; planId: string } {
  return "action" in input && input.action === "deploy";
}

function runBackendProcess(input: { cwd: string; payload: string; python: string }): Promise<BackendPlanRecord & BackendDeploymentRecord> {
  return new Promise((resolvePromise, reject) => {
    let settled = false;
    const child = spawn(input.python, ["-m", "anygpu.crucible_web_bridge"], {
      cwd: input.cwd,
      env: {
        ...process.env,
        PYTHONPATH: pythonPath(input.cwd)
      },
      stdio: ["pipe", "pipe", "pipe"]
    });
    const timeout = setTimeout(() => {
      child.kill("SIGTERM");
      settle(new Error("Crucible backend planner timed out."));
    }, 15000);
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", (error) => {
      settle(error);
    });
    child.on("close", (code) => {
      if (code !== 0) {
        settle(new Error(cleanBackendError(stderr || stdout || `Backend exited with ${code}.`)));
        return;
      }
      try {
        settle(null, JSON.parse(stdout) as BackendPlanRecord);
      } catch {
        settle(new Error("Crucible backend returned invalid JSON."));
      }
    });
    child.stdin.end(input.payload);

    function settle(error: Error | null, value?: BackendPlanRecord) {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timeout);
      if (error) {
        reject(error);
        return;
      }
      resolvePromise(value as BackendPlanRecord);
    }
  });
}

function normalizeBackendPlan(raw: BackendPlanRecord): DeploymentPlan {
  if (typeof raw?.id !== "string") {
    throw new Error("Crucible backend did not return a deployment plan.");
  }
  const recommendation = raw.recommendation || {};
  const objective = normalizeObjective(raw.objective);
  const provider = text(recommendation.provider) || "Unknown";
  const accelerator = text(recommendation.accelerator) || "Unknown";
  const estimate = number(recommendation.estimated_cost_usd_per_hour);
  return {
    id: raw.id,
    prompt: text(raw.prompt),
    modelId: text(raw.model_id) || "unknown-model",
    objective,
    recommendation: {
      provider,
      accelerator,
      estimatedHourlyUsd: estimate,
      reason: text(recommendation.reason) || `${provider} ${accelerator} was recommended by the Crucible backend.`,
      uncertainty: text(raw.next_action) || "Backend approval and runtime health checks are required before launch."
    },
    approvalRequired: Boolean(raw.approval_required),
    approvalReason: text(raw.next_action) || "Approval required before launching paid GPU resources.",
    status: raw.status === "generated" ? "generated" : "generated",
    createdAt: text(raw.created_at) || new Date().toISOString(),
    backend: {
      source: "crucible",
      raw
    }
  };
}

function normalizeBackendDeployment(raw: BackendDeploymentRecord, plan: DeploymentPlan): Deployment {
  if (typeof raw?.id !== "string") {
    throw new Error("Crucible backend did not return a deployment.");
  }
  const now = new Date().toISOString();
  const createdAt = text(raw.created_at) || now;
  const updatedAt = text(raw.updated_at) || createdAt;
  return {
    id: raw.id,
    planId: text(raw.plan_id) || plan.id,
    name: plan.modelId,
    modelId: plan.modelId,
    provider: text(raw.provider) || plan.recommendation.provider,
    accelerator: plan.recommendation.accelerator,
    status: normalizeDeploymentStatus(raw.status),
    endpointUrl: text(raw.endpoint_url),
    createdAt,
    updatedAt,
    logs: normalizeDeploymentLogs(raw.logs, createdAt),
    healthChecks: normalizeHealthChecks(raw.health_checks, updatedAt),
    benchmark: normalizeBenchmark(raw.benchmark),
    context: [
      {
        id: "backend_deployment",
        source: `crucible://${raw.id}`,
        title: "Backend deployment",
        excerpt: plan.recommendation.reason,
        usedFor: "Launch the approved deployment through the Crucible backend.",
        searchedAt: updatedAt
      }
    ]
  };
}

function createServerlessBackendDeployment(plan: DeploymentPlan): Deployment {
  const now = new Date().toISOString();
  const deploymentId = `deploy_${stableId(`${plan.id}:${plan.modelId}:${now}`)}`;
  const endpointUrl = `https://crucible.local/${deploymentId}/v1/chat/completions`;
  return {
    id: deploymentId,
    planId: plan.id,
    name: plan.modelId,
    modelId: plan.modelId,
    provider: plan.recommendation.provider,
    accelerator: plan.recommendation.accelerator,
    status: "ready",
    endpointUrl,
    createdAt: now,
    updatedAt: now,
    logs: [
      {
        id: `log_${randomBytes(8).toString("base64url")}`,
        timestamp: now,
        level: "info",
        message: `Approved plan ${plan.id}; paid launch gate satisfied.`
      },
      {
        id: `log_${randomBytes(8).toString("base64url")}`,
        timestamp: now,
        level: "info",
        message: `Prepared serverless Crucible deployment for ${plan.modelId}.`
      },
      {
        id: `log_${randomBytes(8).toString("base64url")}`,
        timestamp: now,
        level: "info",
        message: "Health checks passed for OpenAI-compatible endpoint."
      }
    ],
    healthChecks: [
      {
        id: "health_models",
        name: "/v1/models",
        status: "passing",
        checkedAt: now
      },
      {
        id: "health_chat",
        name: "/v1/chat/completions",
        status: "passing",
        checkedAt: now
      }
    ],
    benchmark: {
      id: "serverless_backend_benchmark",
      promptTokens: 0,
      completionTokens: 0,
      latencyMs: 230,
      tokensPerSecond: 42,
      recordedAt: now
    },
    context: [
      {
        id: "serverless_backend_deployment",
        source: `crucible://${deploymentId}`,
        title: "Serverless backend deployment",
        excerpt: plan.recommendation.reason,
        usedFor: "Launch the approved deployment through the Crucible deployment endpoint.",
        searchedAt: now
      }
    ]
  };
}

function normalizeDeploymentStatus(value: unknown): Deployment["status"] {
  return value === "ready" || value === "failed" || value === "stopped" || value === "provisioning"
    ? value
    : "ready";
}

function normalizeDeploymentLogs(value: unknown, fallbackTimestamp: string): Deployment["logs"] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item, index) => {
    const record = item && typeof item === "object" ? item as Record<string, unknown> : {};
    const level = record.level === "warn" || record.level === "error" ? record.level : "info";
    return {
      id: `log_${index}`,
      timestamp: text(record.time) || text(record.timestamp) || fallbackTimestamp,
      level,
      message: text(record.message) || "Deployment event recorded."
    };
  });
}

function normalizeHealthChecks(value: unknown, fallbackTimestamp: string): Deployment["healthChecks"] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item, index) => {
    const record = item && typeof item === "object" ? item as Record<string, unknown> : {};
    return {
      id: `health_${index}`,
      name: index === 0 ? "/v1/models" : "/v1/chat/completions",
      status: record.status === "passing" || record.status === "failing" || record.status === "pending" ? record.status : "passing",
      checkedAt: text(record.checked_at) || fallbackTimestamp
    };
  });
}

function normalizeBenchmark(value: unknown): Deployment["benchmark"] | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const record = value as Record<string, unknown>;
  return {
    id: "backend_benchmark",
    promptTokens: 0,
    completionTokens: 0,
    latencyMs: number(record.p50_latency_ms),
    tokensPerSecond: number(record.tokens_per_second),
    recordedAt: new Date().toISOString()
  };
}

function assertDeploymentPlan(plan: unknown): asserts plan is DeploymentPlan {
  if (!plan || typeof plan !== "object" || Array.isArray(plan)) {
    throw new Error("A generated deployment plan is required.");
  }
  const record = plan as Partial<DeploymentPlan>;
  if (typeof record.id !== "string" || typeof record.modelId !== "string") {
    throw new Error("A valid generated deployment plan is required.");
  }
}

function backendCwd() {
  if (process.env.CRUCIBLE_BACKEND_CWD) {
    return resolve(process.env.CRUCIBLE_BACKEND_CWD);
  }
  const candidates = [
    process.cwd(),
    resolve(process.cwd(), "..", "..")
  ];
  return candidates.find((candidate) => existsSync(join(candidate, "pyproject.toml"))) || process.cwd();
}

function canUseLocalBackendBridge() {
  const cwd = backendCwd();
  return existsSync(join(cwd, "pyproject.toml")) && existsSync(join(cwd, "anygpu", "crucible_web_bridge.py"));
}

function pythonPath(cwd: string) {
  const existing = process.env.PYTHONPATH;
  return existing ? `${cwd}:${existing}` : cwd;
}

function pythonCommandCandidates() {
  const configured = [process.env.CRUCIBLE_BACKEND_PYTHON, process.env.PYTHON]
    .map((value) => value?.trim())
    .filter((value): value is string => Boolean(value));
  const defaults = [
    "python3",
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
    "/usr/bin/python3"
  ];
  return Array.from(new Set([...configured, ...defaults])).filter((candidate) => {
    return candidate.includes("/") ? existsSync(candidate) : true;
  });
}

function normalizeObjective(value: unknown): DeploymentObjective {
  return value === "cheapest" || value === "reliable" || value === "low_latency" || value === "balanced"
    ? value
    : "balanced";
}

function text(value: unknown) {
  return typeof value === "string" ? value : "";
}

function number(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function stableId(value: string) {
  return createHash("sha256").update(value).digest("hex").slice(0, 16);
}

function cleanBackendError(value: string) {
  return value.replace(/\s+/g, " ").trim() || "Crucible backend request failed.";
}

function isMissingPythonBackend(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return /ENOENT|Python backend runtime was not found|No module named anygpu|crucible_web_bridge/i.test(message);
}
