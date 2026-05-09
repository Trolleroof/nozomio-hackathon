import type {
  DeploymentObjective,
  DeploymentPlan
} from "@crucible/shared/crucible-contract";
import {
  apiTokens,
  contextSnippets,
  deployments,
  generatedPlan,
  providerCapabilities
} from "@crucible/shared/fixtures";

export interface GenerateDeploymentPlanInput {
  prompt: string;
  modelId: string;
  objective: DeploymentObjective;
  stopPolicy?: string;
}

export function listDeployments() {
  return Promise.resolve(deployments);
}

export function getDeployment(id: string) {
  return Promise.resolve(deployments.find((deployment) => deployment.id === id) ?? deployments[0]);
}

export function listProviderCapabilities() {
  return Promise.resolve(providerCapabilities);
}

export function listContextSnippets() {
  return Promise.resolve(contextSnippets);
}

export function listApiTokens() {
  return Promise.resolve(apiTokens);
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
