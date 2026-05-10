import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

export interface McpDeploymentActivity {
  id: string;
  planId: string;
  status: string;
  endpointUrl: string;
  provider: string;
  runtime: string;
  createdAt: string;
  updatedAt: string;
}

export interface McpRunCapsuleActivity {
  id: string;
  userId: string;
  envContractId: string;
  prompt: string;
  sourceAgent: string;
  status: string;
  provider?: string;
  gpuName?: string;
  phase?: string;
  rewardMean?: number;
  successRate?: number;
  costBurnUsd?: number;
  createdAt: string;
  updatedAt: string;
}

export interface McpActivitySnapshot {
  source: "crucible_mcp";
  deployments: McpDeploymentActivity[];
  runCapsules: McpRunCapsuleActivity[];
  errors: string[];
}

interface RawMcpSnapshot {
  source?: unknown;
  deployments?: unknown;
  run_capsules?: unknown;
  errors?: unknown;
}

export async function listMcpActivity(): Promise<McpActivitySnapshot> {
  try {
    const raw = await runBridgeSnapshot();
    return normalizeSnapshot(raw);
  } catch (error) {
    return {
      source: "crucible_mcp",
      deployments: [],
      runCapsules: [],
      errors: [error instanceof Error ? error.message : "Crucible MCP activity snapshot failed."]
    };
  }
}

function runBridgeSnapshot(): Promise<RawMcpSnapshot> {
  const cwd = backendCwd();
  const python = process.env.CRUCIBLE_BACKEND_PYTHON || process.env.PYTHON || "python3";
  return new Promise((resolvePromise, reject) => {
    const child = spawn(python, ["-m", "anygpu.crucible_web_bridge"], {
      cwd,
      env: {
        ...process.env,
        PYTHONPATH: pythonPath(cwd)
      },
      stdio: ["pipe", "pipe", "pipe"]
    });
    const timeout = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error("Crucible MCP activity snapshot timed out."));
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
      clearTimeout(timeout);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timeout);
      if (code !== 0) {
        reject(new Error(cleanBackendError(stderr || stdout || `Backend exited with ${code}.`)));
        return;
      }
      try {
        resolvePromise(JSON.parse(stdout) as RawMcpSnapshot);
      } catch {
        reject(new Error("Crucible MCP activity snapshot returned invalid JSON."));
      }
    });
    child.stdin.end(JSON.stringify({ action: "mcp_snapshot" }));
  });
}

function normalizeSnapshot(raw: RawMcpSnapshot): McpActivitySnapshot {
  return {
    source: "crucible_mcp",
    deployments: Array.isArray(raw.deployments) ? raw.deployments.map(normalizeDeployment).filter(isDeployment) : [],
    runCapsules: Array.isArray(raw.run_capsules) ? raw.run_capsules.map(normalizeRunCapsule).filter(isRunCapsule) : [],
    errors: Array.isArray(raw.errors) ? raw.errors.filter((error): error is string => typeof error === "string") : []
  };
}

function normalizeDeployment(value: unknown): McpDeploymentActivity | null {
  if (!isRecord(value) || typeof value.id !== "string") {
    return null;
  }
  return {
    id: value.id,
    planId: text(value.plan_id),
    status: text(value.status) || "unknown",
    endpointUrl: text(value.endpoint_url),
    provider: text(value.provider) || "unknown",
    runtime: text(value.runtime) || "unknown",
    createdAt: text(value.created_at) || new Date().toISOString(),
    updatedAt: text(value.updated_at) || text(value.created_at) || new Date().toISOString()
  };
}

function normalizeRunCapsule(value: unknown): McpRunCapsuleActivity | null {
  if (!isRecord(value) || typeof value.id !== "string") {
    return null;
  }
  const metrics = isRecord(value.metrics) ? value.metrics : {};
  return {
    id: value.id,
    userId: text(value.user_id),
    envContractId: text(value.env_contract_id),
    prompt: text(value.prompt),
    sourceAgent: text(value.source_agent) || "mcp",
    status: text(value.status) || "unknown",
    provider: text(value.provider) || undefined,
    gpuName: text(metrics.gpu_name) || undefined,
    phase: text(metrics.latest_phase) || undefined,
    rewardMean: number(metrics.reward_mean),
    successRate: number(metrics.success_rate),
    costBurnUsd: number(metrics.cost_burn_usd),
    createdAt: text(value.created_at) || new Date().toISOString(),
    updatedAt: text(value.updated_at) || text(value.created_at) || new Date().toISOString()
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

function pythonPath(cwd: string) {
  const existing = process.env.PYTHONPATH;
  return existing ? `${cwd}:${existing}` : cwd;
}

function cleanBackendError(value: string) {
  return value.replace(/\s+/g, " ").trim() || "Crucible MCP activity request failed.";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDeployment(value: McpDeploymentActivity | null): value is McpDeploymentActivity {
  return value !== null;
}

function isRunCapsule(value: McpRunCapsuleActivity | null): value is McpRunCapsuleActivity {
  return value !== null;
}

function text(value: unknown) {
  return typeof value === "string" ? value : "";
}

function number(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
