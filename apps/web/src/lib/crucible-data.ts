import type {
  ApiToken,
  Deployment,
  DeploymentLog,
  DeploymentStatus,
  HealthCheck,
  HealthStatus,
  NiaContextSnippet,
  ProviderCapability,
  ProviderStatus
} from "@crucible/shared/crucible-contract";

import { hasNiaApiKey, searchNia } from "./nia-server";

interface GatewayModel {
  id?: unknown;
  anygpu?: {
    health?: unknown;
    provider?: unknown;
    runtime?: unknown;
    simulated?: unknown;
    test_fixture?: unknown;
    upstream_url?: unknown;
  };
}

interface ProviderDefinition {
  provider: string;
  adapter: string;
  env: string[];
  requiresAllEnv?: boolean;
  supportsOpenAIEndpoint: boolean;
  notes: string;
}

const defaultGatewayBaseUrl = "http://127.0.0.1:8765/v1";

const providerDefinitions: ProviderDefinition[] = [
  {
    provider: "Modal",
    adapter: "modal",
    env: ["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"],
    requiresAllEnv: true,
    supportsOpenAIEndpoint: true,
    notes: "Requires Modal credentials before Crucible can deploy a managed vLLM endpoint."
  },
  {
    provider: "RunPod",
    adapter: "runpod",
    env: ["RUNPOD_API_KEY"],
    supportsOpenAIEndpoint: true,
    notes: "Requires a RunPod API key before Crucible can launch pods."
  },
  {
    provider: "Vast.ai",
    adapter: "vast",
    env: ["VAST_AI_API_KEY", "VAST_API_KEY", "ANYGPU_VAST_API_KEY"],
    supportsOpenAIEndpoint: true,
    notes: "Requires a Vast.ai API key before Crucible can launch marketplace instances."
  },
  {
    provider: "Vultr",
    adapter: "vultr",
    env: ["VULTR_API_KEY"],
    supportsOpenAIEndpoint: true,
    notes: "Requires a Vultr API key and GPU availability before Crucible can launch instances."
  },
  {
    provider: "Lambda Cloud",
    adapter: "lambda",
    env: ["LAMBDA_CLOUD_API_KEY", "LAMBDA_API_KEY"],
    supportsOpenAIEndpoint: true,
    notes: "Requires a Lambda API key and SSH key name before Crucible can launch instances."
  },
  {
    provider: "SkyPilot",
    adapter: "skypilot",
    env: ["SKYPILOT_API_SERVER_ENDPOINT"],
    supportsOpenAIEndpoint: true,
    notes: "Requires a configured SkyPilot API server."
  },
  {
    provider: "CoreWeave",
    adapter: "coreweave",
    env: ["COREWEAVE_API_KEY", "COREWEAVE_KUBECONFIG"],
    supportsOpenAIEndpoint: false,
    notes: "Requires CoreWeave credentials or kubeconfig before Crucible can inspect capacity."
  },
  {
    provider: "Tensorlake",
    adapter: "tensorlake",
    env: ["TENSORLAKE_API_KEY"],
    supportsOpenAIEndpoint: false,
    notes: "Requires a Tensorlake API key for sandbox-backed agent execution."
  }
];

export async function listDeployments(): Promise<Deployment[]> {
  const models = await fetchGatewayModels();
  const baseUrl = gatewayBaseUrl();
  return models
    .filter((model) => typeof model.id === "string" && model.id.trim())
    .map((model) => deploymentFromGatewayModel(model, baseUrl));
}

export async function getDeployment(id: string): Promise<Deployment | null> {
  const deployments = await listDeployments();
  return deployments.find((deployment) => deployment.id === id) ?? null;
}

export async function listProviderCapabilities(): Promise<ProviderCapability[]> {
  const models = await fetchGatewayModels();
  const activeProviders = new Set(
    models
      .map((model) => normalizeProvider(String(model.anygpu?.provider ?? "")))
      .filter(Boolean)
  );
  const checkedAt = new Date().toISOString();

  return providerDefinitions.map((definition) => {
    const configured = definition.requiresAllEnv ? hasAllEnv(definition.env) : hasAnyEnv(definition.env);
    const live = activeProviders.has(normalizeProvider(definition.provider));
    const status: ProviderStatus = live ? "live" : configured ? "configured" : "unsupported";
    return {
      id: `provider_${definition.adapter}`,
      provider: definition.provider,
      adapter: definition.adapter,
      status,
      supportsDeploy: configured || live,
      supportsLogs: live,
      supportsStop: live,
      supportsOpenAIEndpoint: definition.supportsOpenAIEndpoint,
      lastCheckedAt: checkedAt,
      lastError: configured || live ? undefined : `Missing ${definition.env.join(" or ")}.`,
      notes: live
        ? "A live AnyGPU gateway model is currently reporting this provider."
        : definition.notes
    };
  });
}

export async function listContextSnippets(): Promise<NiaContextSnippet[]> {
  if (!hasNiaApiKey()) {
    return [];
  }
  const response = await searchNia("Crucible deployment provider health model endpoint readiness");
  return response.snippets;
}

export function listApiTokens(): ApiToken[] {
  const token = process.env.CRUCIBLE_API_TOKEN?.trim();
  if (!token) {
    return [];
  }
  return [
    {
      id: "env_crucible_api_token",
      name: "Deployment environment token",
      prefix: tokenPrefix(token),
      createdAt: new Date().toISOString()
    }
  ];
}

async function fetchGatewayModels(): Promise<GatewayModel[]> {
  try {
    const response = await fetch(`${gatewayBaseUrl()}/models`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2500)
    });
    const body = await response.json();
    if (!response.ok || !Array.isArray(body?.data)) {
      return [];
    }
    return body.data as GatewayModel[];
  } catch {
    return [];
  }
}

function deploymentFromGatewayModel(model: GatewayModel, baseUrl: string): Deployment {
  const now = new Date().toISOString();
  const id = String(model.id);
  const health = typeof model.anygpu?.health === "string" ? model.anygpu.health : "unknown";
  const provider = readableProvider(model.anygpu?.provider);
  const runtime = typeof model.anygpu?.runtime === "string" ? model.anygpu.runtime : "unknown";
  const upstreamUrl = typeof model.anygpu?.upstream_url === "string" ? model.anygpu.upstream_url : undefined;
  const status = deploymentStatusFromHealth(health);
  const healthStatus = healthStatusFromDeploymentStatus(status);
  const simulated = Boolean(model.anygpu?.simulated);
  const testFixture = Boolean(model.anygpu?.test_fixture);

  return {
    id,
    planId: "",
    name: id,
    modelId: id,
    provider,
    accelerator: "reported by provider",
    status,
    endpointUrl: baseUrl,
    createdAt: now,
    updatedAt: now,
    logs: [
      gatewayLog(
        "gateway_status",
        now,
        healthStatus === "passing" ? "info" : healthStatus === "failing" ? "error" : "warn",
        `Gateway reported ${id} on ${provider} with ${runtime}; route mode is ${testFixture ? "test fixture" : simulated ? "simulated" : "real runtime"}.`
      )
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
        status: healthStatus,
        checkedAt: now
      }
    ],
    benchmark: undefined,
    context: upstreamUrl
      ? [
          {
            id: "gateway_upstream",
            source: upstreamUrl,
            title: "Gateway upstream runtime",
            excerpt: upstreamUrl,
            usedFor: "Show the real runtime URL that the AnyGPU gateway is routing to.",
            searchedAt: now
          }
        ]
      : []
  };
}

function gatewayLog(id: string, timestamp: string, level: DeploymentLog["level"], message: string): DeploymentLog {
  return { id, timestamp, level, message };
}

function deploymentStatusFromHealth(health: string): DeploymentStatus {
  const normalized = health.toLowerCase();
  if (["healthy", "ready", "passing"].includes(normalized)) {
    return "ready";
  }
  if (["stopped", "stopping"].includes(normalized)) {
    return normalized as DeploymentStatus;
  }
  if (["failed", "unhealthy", "error"].includes(normalized)) {
    return "failed";
  }
  if (["provisioning", "starting", "pending"].includes(normalized)) {
    return "provisioning";
  }
  return "health_checking";
}

function healthStatusFromDeploymentStatus(status: DeploymentStatus): HealthStatus {
  if (status === "ready") {
    return "passing";
  }
  if (status === "failed") {
    return "failing";
  }
  if (status === "stopped") {
    return "not_run";
  }
  return "pending";
}

function gatewayBaseUrl() {
  return (process.env.ANYGPU_GATEWAY_BASE_URL || defaultGatewayBaseUrl).replace(/\/$/, "");
}

function hasAnyEnv(names: string[]) {
  return names.some((name) => Boolean(process.env[name]?.trim()));
}

function hasAllEnv(names: string[]) {
  return names.every((name) => Boolean(process.env[name]?.trim()));
}

function readableProvider(value: unknown) {
  if (typeof value !== "string" || !value.trim()) {
    return "AnyGPU";
  }
  const normalized = normalizeProvider(value);
  const known = providerDefinitions.find((definition) => normalizeProvider(definition.provider) === normalized);
  return known?.provider ?? value;
}

function normalizeProvider(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function tokenPrefix(token: string) {
  const trimmed = token.trim();
  if (trimmed.length <= 12) {
    return trimmed;
  }
  return `${trimmed.slice(0, 12)}...`;
}
