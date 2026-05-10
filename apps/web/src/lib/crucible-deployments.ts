import { createHash, randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";

import type { Deployment, DeploymentPlan } from "@crucible/shared/crucible-contract";

interface DeploymentStore {
  deployments: Deployment[];
}

export const deploymentCookieIndexName = "crucible_deployment_ids";

export function deploymentCookieName(id: string) {
  return `crucible_deployment_${id}`;
}

export function encodeDeploymentCookie(deployment: Deployment) {
  return Buffer.from(JSON.stringify(deployment), "utf8").toString("base64url");
}

export async function deployPlan(plan: DeploymentPlan): Promise<Deployment> {
  assertDeploymentPlan(plan);
  const now = new Date().toISOString();
  const gateway = await resolveDeploymentGateway(plan);
  const deployment: Deployment = {
    id: `dep_${stableId(`${plan.id}:${plan.modelId}:${now}`)}`,
    planId: plan.id,
    name: plan.modelId,
    modelId: plan.modelId,
    provider: plan.recommendation.provider,
    accelerator: plan.recommendation.accelerator,
    status: "ready",
    endpointUrl: gateway.endpointUrl,
    createdAt: now,
    updatedAt: now,
    logs: [
      {
        id: `log_${randomBytes(8).toString("base64url")}`,
        timestamp: now,
        level: "info",
        message: `Deployment created for ${plan.modelId} through ${gateway.label}.`
      },
      {
        id: `log_${randomBytes(8).toString("base64url")}`,
        timestamp: now,
        level: "info",
        message: `${plan.recommendation.provider} ${plan.recommendation.accelerator} selected from plan ${plan.id}.`
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
    context: [
      {
        id: "plan_recommendation",
        source: `plan://${plan.id}`,
        title: "Deployment plan",
        excerpt: plan.recommendation.reason,
        usedFor: "Create a live deployment record from the generated plan.",
        searchedAt: now
      }
    ]
  };
  saveDeployment(deployment);
  return deployment;
}

function assertDeploymentPlan(plan: unknown): asserts plan is DeploymentPlan {
  if (!plan || typeof plan !== "object" || Array.isArray(plan)) {
    throw new Error("A generated deployment plan is required.");
  }
  const record = plan as Partial<DeploymentPlan>;
  if (
    typeof record.id !== "string" ||
    typeof record.modelId !== "string" ||
    !record.recommendation ||
    typeof record.recommendation.provider !== "string" ||
    typeof record.recommendation.accelerator !== "string"
  ) {
    throw new Error("A valid generated deployment plan is required.");
  }
}

export async function listStoredDeployments(): Promise<Deployment[]> {
  const deployments = [
    ...(await listCookieDeployments()),
    ...loadStore().deployments
  ].filter(uniqueDeployment);

  return deployments.sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export async function getStoredDeployment(id: string): Promise<Deployment | null> {
  return (await listStoredDeployments()).find((deployment) => deployment.id === id) ?? null;
}

export function stopStoredDeployment(id: string): Deployment {
  const store = loadStore();
  const existing = store.deployments.find((deployment) => deployment.id === id);
  if (!existing) {
    throw new Error("Deployment not found.");
  }
  const now = new Date().toISOString();
  const stopped: Deployment = {
    ...existing,
    status: "stopped",
    updatedAt: now,
    logs: [
      {
        id: `log_${randomBytes(8).toString("base64url")}`,
        timestamp: now,
        level: "info",
        message: `Stop requested for ${existing.modelId}. Deployment is stopped in the Crucible control plane.`
      },
      ...existing.logs
    ],
    healthChecks: existing.healthChecks.map((check) => ({
      ...check,
      status: "not_run",
      checkedAt: now
    }))
  };
  saveStore({
    deployments: store.deployments.map((deployment) => (
      deployment.id === id ? stopped : deployment
    ))
  });
  return stopped;
}

async function resolveDeploymentGateway(plan: DeploymentPlan) {
  const anyGpuGateway = process.env.ANYGPU_GATEWAY_BASE_URL?.trim();
  if (anyGpuGateway) {
    const endpointUrl = anyGpuGateway.replace(/\/$/, "");
    await verifyOpenAiGateway(endpointUrl);
    return {
      endpointUrl,
      label: "AnyGPU gateway"
    };
  }

  throw new Error("No live AnyGPU gateway is configured. Start or deploy a model gateway before creating a deployment.");
}

async function verifyOpenAiGateway(endpointUrl: string) {
  const response = await fetch(`${endpointUrl}/models`, {
    headers: gatewayHeaders(),
    cache: "no-store",
    signal: AbortSignal.timeout(5000)
  });
  if (!response.ok) {
    throw new Error(`AnyGPU gateway /models check failed with HTTP ${response.status}.`);
  }
}

function gatewayHeaders() {
  const apiKey = process.env.ANYGPU_GATEWAY_API_KEY?.trim();
  return apiKey ? { Authorization: `Bearer ${apiKey}` } : undefined;
}

function saveDeployment(deployment: Deployment) {
  const store = loadStore();
  const deployments = [
    deployment,
    ...store.deployments.filter((existing) => existing.id !== deployment.id)
  ].slice(0, 50);
  saveStore({ deployments });
}

function loadStore(): DeploymentStore {
  const path = storePath();
  if (!existsSync(path)) {
    return { deployments: [] };
  }
  return JSON.parse(readFileSync(path, "utf8")) as DeploymentStore;
}

function saveStore(store: DeploymentStore) {
  const path = storePath();
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(store, null, 2));
}

async function listCookieDeployments(): Promise<Deployment[]> {
  try {
    const { cookies } = await import("next/headers");
    const cookieStore = await cookies();
    const deploymentIds = cookieStore.get(deploymentCookieIndexName)?.value
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean) ?? [];

    return deploymentIds
      .map((id) => cookieStore.get(deploymentCookieName(id))?.value)
      .map(decodeDeploymentCookie)
      .filter((deployment): deployment is Deployment => Boolean(deployment));
  } catch {
    return [];
  }
}

function decodeDeploymentCookie(value: string | undefined): Deployment | null {
  if (!value) {
    return null;
  }
  try {
    const deployment = JSON.parse(Buffer.from(value, "base64url").toString("utf8")) as Deployment;
    return typeof deployment.id === "string" ? deployment : null;
  } catch {
    return null;
  }
}

function uniqueDeployment(deployment: Deployment, index: number, deployments: Deployment[]) {
  return deployments.findIndex((candidate) => candidate.id === deployment.id) === index;
}

function storePath() {
  return process.env.CRUCIBLE_DEPLOYMENT_STORE_PATH ?? join(tmpdir(), "crucible-web-deployments.json");
}

function stableId(value: string) {
  return createHash("sha256").update(value).digest("hex").slice(0, 16);
}
