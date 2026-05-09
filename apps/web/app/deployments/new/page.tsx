"use client";

import type { DeploymentObjective, DeploymentPlan } from "@crucible/shared/crucible-contract";
import { Cpu, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { AppFrame } from "@/components/app-frame";
import { StatusBadge } from "@/components/status-badge";
import { generateDeploymentPlan } from "@/lib/crucible-client";
import { formatCurrency } from "@/lib/format";

const defaultPrompt = "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.";
const objectives: { value: DeploymentObjective; label: string }[] = [
  { value: "cheapest", label: "cheapest" },
  { value: "reliable", label: "reliable" },
  { value: "low_latency", label: "low latency" },
  { value: "balanced", label: "balanced" }
];

export default function NewDeploymentPage() {
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [modelId, setModelId] = useState("Qwen/Qwen2.5-7B-Instruct");
  const [objective, setObjective] = useState<DeploymentObjective>("cheapest");
  const [stopPolicy, setStopPolicy] = useState("manual");
  const [plan, setPlan] = useState<DeploymentPlan | null>(null);

  async function handleGenerate() {
    const nextPlan = await generateDeploymentPlan({ prompt, modelId, objective, stopPolicy });
    setPlan(nextPlan);
  }

  return (
    <AppFrame>
      <div className="mb-8">
        <h1 className="text-2xl font-medium tracking-tight">New deployment</h1>
      </div>

      <div className="grid items-start gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <section className="crucible-card">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium" htmlFor="deployment-request">
                Deployment request
              </label>
              <textarea
                id="deployment-request"
                className="crucible-textarea mt-2 min-h-32 w-full"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium" htmlFor="model-id">
                Model ID
              </label>
              <input
                id="model-id"
                className="crucible-input mt-2 min-h-11 w-full"
                value={modelId}
                onChange={(event) => setModelId(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium" htmlFor="objective">
                Objective
              </label>
              <select
                id="objective"
                className="crucible-input mt-2 min-h-11 w-full"
                value={objective}
                onChange={(event) => setObjective(event.target.value as DeploymentObjective)}
              >
                {objectives.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium" htmlFor="stop-policy">
                Stop policy
              </label>
              <select
                id="stop-policy"
                className="crucible-input mt-2 min-h-11 w-full"
                value={stopPolicy}
                onChange={(event) => setStopPolicy(event.target.value)}
              >
                <option value="manual">Manual stop only</option>
                <option value="idle_30">Stop after 30 idle minutes</option>
                <option value="demo_window">Stop after judge demo window</option>
              </select>
            </div>
            <button
              className="crucible-primary min-h-11 gap-2 px-5"
              type="button"
              onClick={handleGenerate}
            >
              <Cpu aria-hidden="true" className="h-4 w-4" />
              Generate plan
            </button>
          </div>
        </section>

        <section className="crucible-card-muted">
          <h2 className="text-lg font-semibold tracking-tight">Plan preview</h2>
          {plan ? (
            <div className="mt-4 space-y-5">
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge status="approval_required">Approval required</StatusBadge>
                <span className="text-sm text-muted-foreground">Paid GPU launch needs human approval before provisioning.</span>
              </div>
              <dl className="divide-y divide-border text-sm">
                <div className="grid gap-2 py-3 sm:grid-cols-[9rem_1fr]">
                  <dt className="text-muted-foreground">Provider</dt>
                  <dd className="font-medium">{plan.recommendation.provider}</dd>
                </div>
                <div className="grid gap-2 py-3 sm:grid-cols-[9rem_1fr]">
                  <dt className="text-muted-foreground">Accelerator</dt>
                  <dd className="font-medium">{plan.recommendation.accelerator}</dd>
                </div>
                <div className="grid gap-2 py-3 sm:grid-cols-[9rem_1fr]">
                  <dt className="text-muted-foreground">Estimate</dt>
                  <dd className="font-medium">{formatCurrency(plan.recommendation.estimatedHourlyUsd)}/hr</dd>
                </div>
                <div className="grid gap-2 py-3 sm:grid-cols-[9rem_1fr]">
                  <dt className="text-muted-foreground">Model</dt>
                  <dd className="break-words font-medium">{plan.modelId}</dd>
                </div>
              </dl>
              <div>
                <h3 className="text-sm font-medium">Recommendation</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{plan.recommendation.reason}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium">Uncertainty</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{plan.recommendation.uncertainty}</p>
              </div>
              <button
                className="crucible-secondary min-h-10 gap-2"
                type="button"
              >
                <ShieldCheck aria-hidden="true" className="h-4 w-4" />
                Request approval
              </button>
            </div>
          ) : (
            <div className="mt-4 max-w-md text-sm leading-6 text-muted-foreground">
              Generate a plan to see provider choice, GPU estimate, uncertainty, and the approval gate.
            </div>
          )}
        </section>
      </div>
    </AppFrame>
  );
}
