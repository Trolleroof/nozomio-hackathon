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
  return Promise.resolve({
    ...generatedPlan,
    prompt: input.prompt || generatedPlan.prompt,
    modelId: input.modelId || generatedPlan.modelId,
    objective: input.objective
  });
}
