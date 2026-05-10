import type { DeploymentObjective, DeploymentPlan, DeploymentStatus } from "@crucible/shared/crucible-contract";

export const onboardingLaunchStorageKey = "crucible:onboarding-launch";
export const onboardingCompleteStorageKey = "crucible:onboarding-complete";

export interface OnboardingLaunch {
  id: string;
  planId: string;
  name: string;
  modelId: string;
  objective: DeploymentObjective;
  provider: string;
  accelerator: string;
  estimatedHourlyUsd: number;
  status: DeploymentStatus;
  createdAt: string;
}

export function createOnboardingLaunch(plan: DeploymentPlan, modelName: string): OnboardingLaunch {
  return {
    id: `launch_${plan.id}`,
    planId: plan.id,
    name: `${modelName} first run`,
    modelId: plan.modelId,
    objective: plan.objective,
    provider: plan.recommendation.provider,
    accelerator: plan.recommendation.accelerator,
    estimatedHourlyUsd: plan.recommendation.estimatedHourlyUsd,
    status: "provisioning",
    createdAt: new Date().toISOString()
  };
}

export function readOnboardingLaunch(storage: Storage): OnboardingLaunch | null {
  const raw = storage.getItem(onboardingLaunchStorageKey);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Partial<OnboardingLaunch>;
    if (!parsed.modelId || !parsed.provider || !parsed.accelerator || !parsed.status) {
      return null;
    }
    return parsed as OnboardingLaunch;
  } catch {
    return null;
  }
}

export function objectiveLabel(objective: DeploymentObjective) {
  if (objective === "cheapest") {
    return "price";
  }
  if (objective === "low_latency") {
    return "latency";
  }
  if (objective === "reliable") {
    return "reliability";
  }
  return "balance";
}
