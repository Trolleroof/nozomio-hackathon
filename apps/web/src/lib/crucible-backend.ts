import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

import type {
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

async function runLocalBackendBridge(input: BackendDeploymentPlanInput): Promise<BackendPlanRecord> {
  const cwd = backendCwd();
  const payload = JSON.stringify({
    action: "plan",
    userId: input.userId,
    email: input.email,
    prompt: input.prompt,
    modelId: input.modelId,
    objective: input.objective,
    sourceAgent: input.sourceAgent || "web"
  });
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

function runBackendProcess(input: { cwd: string; payload: string; python: string }): Promise<BackendPlanRecord> {
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

function cleanBackendError(value: string) {
  return value.replace(/\s+/g, " ").trim() || "Crucible backend request failed.";
}

function isMissingPythonBackend(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return /ENOENT|Python backend runtime was not found|No module named anygpu|crucible_web_bridge/i.test(message);
}
