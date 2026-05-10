export type UserRole = "user" | "admin";

export type DeploymentObjective =
  | "cheapest"
  | "reliable"
  | "low_latency"
  | "balanced";

export type ProviderStatus =
  | "live"
  | "dry_run_only"
  | "configured"
  | "unsupported"
  | "failed";

export type DeploymentStatus =
  | "draft"
  | "approval_required"
  | "approved"
  | "queued"
  | "provisioning"
  | "health_checking"
  | "ready"
  | "failed"
  | "stopping"
  | "stopped";

export type HealthStatus = "pending" | "passing" | "failing" | "not_run";

export interface ProviderCapability {
  id: string;
  provider: string;
  adapter: string;
  status: ProviderStatus;
  supportsDeploy: boolean;
  supportsLogs: boolean;
  supportsStop: boolean;
  supportsOpenAIEndpoint: boolean;
  lastCheckedAt: string;
  lastError?: string;
  notes: string;
}

export interface DeploymentPlan {
  id: string;
  prompt: string;
  modelId: string;
  objective: DeploymentObjective;
  recommendation: {
    provider: string;
    accelerator: string;
    estimatedHourlyUsd: number;
    reason: string;
    uncertainty: string;
  };
  approvalRequired: boolean;
  approvalReason: string;
  status: "generated" | "needs_clarification" | "error";
  createdAt: string;
  memoryInsights?: string[];
  backend?: {
    source: string;
    raw?: unknown;
  };
}

export interface DeploymentLog {
  id: string;
  timestamp: string;
  level: "info" | "warn" | "error";
  message: string;
}

export interface HealthCheck {
  id: string;
  name: "/v1/models" | "/v1/chat/completions";
  status: HealthStatus;
  latencyMs?: number;
  checkedAt?: string;
}

export interface BenchmarkResult {
  id: string;
  promptTokens: number;
  completionTokens: number;
  latencyMs: number;
  tokensPerSecond: number;
  recordedAt: string;
}

export interface NiaContextSnippet {
  id: string;
  source: string;
  title: string;
  excerpt: string;
  usedFor: string;
  searchedAt: string;
}

export interface Deployment {
  id: string;
  planId: string;
  name: string;
  modelId: string;
  provider: string;
  accelerator: string;
  status: DeploymentStatus;
  endpointUrl?: string;
  createdAt: string;
  updatedAt: string;
  logs: DeploymentLog[];
  healthChecks: HealthCheck[];
  benchmark?: BenchmarkResult;
  context: NiaContextSnippet[];
}

export interface ApiToken {
  id: string;
  name: string;
  prefix: string;
  createdAt: string;
  lastUsedAt?: string;
}
