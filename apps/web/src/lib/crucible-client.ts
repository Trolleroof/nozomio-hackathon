import type {
  ApiToken,
  Deployment,
  DeploymentObjective,
  DeploymentPlan,
  NiaContextSnippet,
  ProviderCapability
} from "@crucible/shared/crucible-contract";

export interface GenerateDeploymentPlanInput {
  prompt?: string;
  modelId: string;
  objective: DeploymentObjective;
  notes?: string;
  stopPolicy?: string;
}

export function listDeployments() {
  return Promise.resolve([] satisfies Deployment[]);
}

export function getDeployment(id: string) {
  void id;
  return Promise.resolve(null as Deployment | null);
}

export function listProviderCapabilities() {
  return Promise.resolve([] satisfies ProviderCapability[]);
}

export function listContextSnippets() {
  return Promise.resolve([] satisfies NiaContextSnippet[]);
}

export function listApiTokens() {
  return Promise.resolve([] satisfies ApiToken[]);
}

export function generateDeploymentPlan(input: GenerateDeploymentPlanInput): Promise<DeploymentPlan> {
  return fetch("/api/crucible/plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  }).then(async (response) => {
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Plan generation failed.");
    }
    return body as DeploymentPlan;
  });
}

export function deployDeploymentPlan(plan: DeploymentPlan): Promise<Deployment> {
  return fetch("/api/crucible/deploy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan })
  }).then(async (response) => {
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Deployment failed.");
    }
    return body.deployment as Deployment;
  });
}
