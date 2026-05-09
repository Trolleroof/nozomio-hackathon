import type {
  ApiToken,
  Deployment,
  DeploymentPlan,
  NiaContextSnippet,
  ProviderCapability
} from "./crucible-contract";

export const generatedPlan: DeploymentPlan = {
  id: "plan_qwen_7b",
  prompt: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
  modelId: "Qwen/Qwen2.5-7B-Instruct",
  objective: "cheapest",
  recommendation: {
    provider: "Modal",
    accelerator: "NVIDIA L4",
    estimatedHourlyUsd: 0.8,
    reason:
      "Modal is the only live frontend-supported path in this demo, and an L4 is a realistic low-cost target for a quantized Qwen 7B deployment.",
    uncertainty:
      "Final memory fit, exact price, and cold-start behavior must be confirmed by the backend worker before paid launch."
  },
  approvalRequired: true,
  approvalReason:
    "Approval required before launching paid GPU resources from a personal agent.",
  status: "generated",
  createdAt: "2026-05-09T16:00:00.000Z"
};

export const contextSnippets: NiaContextSnippet[] = [
  {
    id: "ctx_skypilot",
    source: "nia://repo/docs/skypilot",
    title: "SkyPilot docs",
    excerpt:
      "SkyPilot examples are indexed for planning only until the worker can validate live credentials and provider quotas.",
    usedFor: "Explain why SkyPilot is shown as dry-run only.",
    searchedAt: "2026-05-09T16:03:00.000Z"
  },
  {
    id: "ctx_vllm",
    source: "nia://repo/docs/vllm",
    title: "vLLM docs",
    excerpt:
      "OpenAI-compatible endpoints expose model listing and chat completions routes for health checks.",
    usedFor: "Choose the endpoint and health-check shape.",
    searchedAt: "2026-05-09T16:04:00.000Z"
  },
  {
    id: "ctx_modal_vllm",
    source: "nia://repo/examples/modal-vllm",
    title: "Modal vLLM docs",
    excerpt:
      "Modal is represented as the demo live adapter while the frontend waits for backend deployment APIs.",
    usedFor: "Support the Modal recommendation in the generated plan.",
    searchedAt: "2026-05-09T16:05:00.000Z"
  },
  {
    id: "ctx_recipes",
    source: "nia://repo/recipes",
    title: "known working recipes",
    excerpt:
      "Known working recipes favor small safe models for demos and require approval before larger paid GPU launches.",
    usedFor: "Keep the details page on a safe live model while the wizard plans Qwen 7B.",
    searchedAt: "2026-05-09T16:06:00.000Z"
  }
];

export const providerCapabilities: ProviderCapability[] = [
  {
    id: "provider_modal",
    provider: "Modal",
    adapter: "modal",
    status: "live",
    supportsDeploy: true,
    supportsLogs: true,
    supportsStop: true,
    supportsOpenAIEndpoint: true,
    lastCheckedAt: "2026-05-09T15:55:00.000Z",
    notes: "Modal is the only live launch path represented by the frontend demo contract."
  },
  {
    id: "provider_skypilot",
    provider: "SkyPilot",
    adapter: "skypilot",
    status: "dry_run_only",
    supportsDeploy: false,
    supportsLogs: false,
    supportsStop: false,
    supportsOpenAIEndpoint: true,
    lastCheckedAt: "2026-05-09T15:56:00.000Z",
    notes: "Planning-only dry run until worker credentials are available."
  },
  {
    id: "provider_lambda",
    provider: "Lambda Cloud",
    adapter: "manual",
    status: "configured",
    supportsDeploy: false,
    supportsLogs: false,
    supportsStop: false,
    supportsOpenAIEndpoint: true,
    lastCheckedAt: "2026-05-09T15:57:00.000Z",
    notes: "Configured; waiting for worker validation."
  },
  {
    id: "provider_prime",
    provider: "Prime Intellect",
    adapter: "manual",
    status: "configured",
    supportsDeploy: false,
    supportsLogs: false,
    supportsStop: false,
    supportsOpenAIEndpoint: true,
    lastCheckedAt: "2026-05-09T15:58:00.000Z",
    notes: "Configured; waiting for worker validation."
  },
  {
    id: "provider_coreweave",
    provider: "CoreWeave",
    adapter: "manual",
    status: "configured",
    supportsDeploy: false,
    supportsLogs: false,
    supportsStop: false,
    supportsOpenAIEndpoint: true,
    lastCheckedAt: "2026-05-09T15:59:00.000Z",
    notes: "Configured; waiting for worker validation."
  },
  {
    id: "provider_vast",
    provider: "Vast.ai",
    adapter: "manual",
    status: "failed",
    supportsDeploy: false,
    supportsLogs: false,
    supportsStop: false,
    supportsOpenAIEndpoint: false,
    lastCheckedAt: "2026-05-09T16:00:00.000Z",
    lastError: "Credentials missing for VAST_AI_API_KEY.",
    notes: "Unsupported until credentials and launch templates are validated."
  },
  {
    id: "provider_vultr",
    provider: "Vultr",
    adapter: "manual",
    status: "unsupported",
    supportsDeploy: false,
    supportsLogs: false,
    supportsStop: false,
    supportsOpenAIEndpoint: false,
    lastCheckedAt: "2026-05-09T16:01:00.000Z",
    lastError: "GPU entitlement is blocked for the demo account.",
    notes: "Unsupported until account entitlement is confirmed."
  }
];

export const deployments: Deployment[] = [
  {
    id: "dep_qwen_modal",
    planId: "plan_safe_modal",
    name: "Qwen safe Modal demo",
    modelId: "Qwen/Qwen2.5-0.5B-Instruct",
    provider: "Modal",
    accelerator: "NVIDIA L4",
    status: "ready",
    endpointUrl: "https://dep-qwen-modal.crucible.example/v1",
    createdAt: "2026-05-09T14:30:00.000Z",
    updatedAt: "2026-05-09T15:15:00.000Z",
    logs: [
      {
        id: "log_ready_1",
        timestamp: "2026-05-09T14:32:00.000Z",
        level: "info",
        message: "Plan approved for safe fixture deployment."
      },
      {
        id: "log_ready_2",
        timestamp: "2026-05-09T14:36:00.000Z",
        level: "info",
        message: "Provisioned Modal container with vLLM OpenAI-compatible server."
      },
      {
        id: "log_ready_3",
        timestamp: "2026-05-09T14:40:00.000Z",
        level: "info",
        message: "Health checks passed for /v1/models and /v1/chat/completions."
      }
    ],
    healthChecks: [
      {
        id: "health_models_ready",
        name: "/v1/models",
        status: "passing",
        latencyMs: 82,
        checkedAt: "2026-05-09T14:40:00.000Z"
      },
      {
        id: "health_chat_ready",
        name: "/v1/chat/completions",
        status: "passing",
        latencyMs: 418,
        checkedAt: "2026-05-09T14:40:20.000Z"
      }
    ],
    benchmark: {
      id: "bench_ready_1",
      promptTokens: 88,
      completionTokens: 164,
      latencyMs: 1840,
      tokensPerSecond: 89.1,
      recordedAt: "2026-05-09T14:42:00.000Z"
    },
    context: contextSnippets
  },
  {
    id: "dep_qwen_approval",
    planId: "plan_qwen_7b",
    name: "Qwen 7B approval gate",
    modelId: "Qwen/Qwen2.5-7B-Instruct",
    provider: "Modal",
    accelerator: "NVIDIA L4",
    status: "approval_required",
    createdAt: "2026-05-09T16:00:00.000Z",
    updatedAt: "2026-05-09T16:02:00.000Z",
    logs: [
      {
        id: "log_approval_1",
        timestamp: "2026-05-09T16:00:30.000Z",
        level: "warn",
        message: "Approval required before launching GPU resources."
      }
    ],
    healthChecks: [
      {
        id: "health_models_pending",
        name: "/v1/models",
        status: "not_run"
      },
      {
        id: "health_chat_pending",
        name: "/v1/chat/completions",
        status: "not_run"
      }
    ],
    context: contextSnippets
  },
  {
    id: "dep_modal_provisioning",
    planId: "plan_modal_provisioning",
    name: "Modal Qwen provisioning",
    modelId: "Qwen/Qwen2.5-7B-Instruct",
    provider: "Modal",
    accelerator: "NVIDIA L4",
    status: "provisioning",
    createdAt: "2026-05-09T15:48:00.000Z",
    updatedAt: "2026-05-09T15:54:00.000Z",
    logs: [
      {
        id: "log_provisioning_1",
        timestamp: "2026-05-09T15:49:00.000Z",
        level: "info",
        message: "Queued Modal dry-run launch from the approved demo plan."
      },
      {
        id: "log_provisioning_2",
        timestamp: "2026-05-09T15:54:00.000Z",
        level: "info",
        message: "Provisioning worker is preparing the OpenAI-compatible endpoint."
      }
    ],
    healthChecks: [
      {
        id: "health_models_provisioning",
        name: "/v1/models",
        status: "pending"
      },
      {
        id: "health_chat_provisioning",
        name: "/v1/chat/completions",
        status: "pending"
      }
    ],
    context: contextSnippets.slice(1)
  },
  {
    id: "dep_sky_failed",
    planId: "plan_sky_failed",
    name: "SkyPilot dry-run failure",
    modelId: "Qwen/Qwen2.5-7B-Instruct",
    provider: "SkyPilot",
    accelerator: "NVIDIA A10G",
    status: "failed",
    createdAt: "2026-05-09T13:30:00.000Z",
    updatedAt: "2026-05-09T13:44:00.000Z",
    logs: [
      {
        id: "log_failed_1",
        timestamp: "2026-05-09T13:35:00.000Z",
        level: "info",
        message: "Dry-run produced a candidate plan."
      },
      {
        id: "log_failed_2",
        timestamp: "2026-05-09T13:44:00.000Z",
        level: "error",
        message: "Worker API unavailable; live SkyPilot deploy is not enabled."
      }
    ],
    healthChecks: [
      {
        id: "health_models_failed",
        name: "/v1/models",
        status: "failing",
        checkedAt: "2026-05-09T13:44:00.000Z"
      },
      {
        id: "health_chat_failed",
        name: "/v1/chat/completions",
        status: "not_run"
      }
    ],
    context: contextSnippets.slice(0, 2)
  },
  {
    id: "dep_vultr_stopped",
    planId: "plan_vultr_stopped",
    name: "Vultr entitlement check",
    modelId: "Qwen/Qwen2.5-0.5B-Instruct",
    provider: "Vultr",
    accelerator: "NVIDIA A40",
    status: "stopped",
    createdAt: "2026-05-09T11:10:00.000Z",
    updatedAt: "2026-05-09T11:50:00.000Z",
    logs: [
      {
        id: "log_stopped_1",
        timestamp: "2026-05-09T11:20:00.000Z",
        level: "warn",
        message: "Provider entitlement blocked the launch before any GPU resources started."
      },
      {
        id: "log_stopped_2",
        timestamp: "2026-05-09T11:50:00.000Z",
        level: "info",
        message: "Deployment marked stopped with no live endpoint."
      }
    ],
    healthChecks: [
      {
        id: "health_models_stopped",
        name: "/v1/models",
        status: "not_run"
      },
      {
        id: "health_chat_stopped",
        name: "/v1/chat/completions",
        status: "not_run"
      }
    ],
    context: contextSnippets.slice(0, 1)
  }
];

export const apiTokens: ApiToken[] = [
  {
    id: "token_demo",
    name: "Demo agent token",
    prefix: "cru_demo_7d4f",
    createdAt: "2026-05-09T12:00:00.000Z",
    lastUsedAt: "2026-05-09T16:10:00.000Z"
  }
];
