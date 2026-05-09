"use client";

import type { DeploymentObjective, DeploymentPlan } from "@crucible/shared/crucible-contract";
import { AlertTriangle, BadgeDollarSign, Cpu, ShieldCheck } from "lucide-react";
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
        <p className="text-sm text-zinc-500">Mock planning, real contract shape</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">New deployment</h1>
      </div>

      <div className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="rounded-md border border-zinc-200 bg-white p-5">
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium" htmlFor="deployment-request">
                Deployment request
              </label>
              <textarea
                id="deployment-request"
                className="mt-2 min-h-32 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-950"
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
                className="mt-2 min-h-11 w-full rounded-md border border-zinc-300 px-3 text-sm outline-none focus:border-zinc-950"
                value={modelId}
                onChange={(event) => setModelId(event.target.value)}
              />
            </div>
            <fieldset>
              <legend className="text-sm font-medium">Objective</legend>
              <div className="mt-2 grid gap-2 sm:grid-cols-4">
                {objectives.map((item) => (
                  <label
                    key={item.value}
                    className={`flex min-h-10 cursor-pointer items-center justify-center rounded-md border px-3 text-sm ${
                      objective === item.value ? "border-zinc-950 bg-zinc-950 text-white" : "border-zinc-300 bg-white"
                    }`}
                  >
                    <input
                      className="sr-only"
                      name="objective"
                      type="radio"
                      value={item.value}
                      checked={objective === item.value}
                      onChange={() => setObjective(item.value)}
                    />
                    {item.label}
                  </label>
                ))}
              </div>
            </fieldset>
            <div>
              <label className="block text-sm font-medium" htmlFor="stop-policy">
                Stop policy
              </label>
              <select
                id="stop-policy"
                className="mt-2 min-h-11 w-full rounded-md border border-zinc-300 px-3 text-sm outline-none focus:border-zinc-950"
                value={stopPolicy}
                onChange={(event) => setStopPolicy(event.target.value)}
              >
                <option value="manual">Manual stop only</option>
                <option value="idle_30">Stop after 30 idle minutes</option>
                <option value="demo_window">Stop after judge demo window</option>
              </select>
            </div>
            <button
              className="inline-flex min-h-11 items-center gap-2 rounded-md bg-zinc-950 px-5 py-2 text-sm font-medium text-white hover:bg-zinc-800"
              type="button"
              onClick={handleGenerate}
            >
              <Cpu aria-hidden="true" className="h-4 w-4" />
              Generate plan
            </button>
          </div>
        </section>

        <section className="rounded-md border border-zinc-200 bg-zinc-50 p-5">
          <h2 className="text-lg font-semibold tracking-tight">Plan preview</h2>
          {plan ? (
            <div className="mt-4 space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge status="approval_required">Approval required</StatusBadge>
                <span className="text-sm text-zinc-600">Paid GPU launch needs human approval before provisioning.</span>
              </div>
              <dl className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-md border border-zinc-200 bg-white p-4">
                  <dt className="text-xs uppercase tracking-wide text-zinc-500">Provider</dt>
                  <dd className="mt-1 font-medium">{plan.recommendation.provider}</dd>
                </div>
                <div className="rounded-md border border-zinc-200 bg-white p-4">
                  <dt className="text-xs uppercase tracking-wide text-zinc-500">Accelerator</dt>
                  <dd className="mt-1 font-medium">{plan.recommendation.accelerator}</dd>
                </div>
                <div className="rounded-md border border-zinc-200 bg-white p-4">
                  <dt className="text-xs uppercase tracking-wide text-zinc-500">Estimate</dt>
                  <dd className="mt-1 font-medium">{formatCurrency(plan.recommendation.estimatedHourlyUsd)}/hr</dd>
                </div>
                <div className="rounded-md border border-zinc-200 bg-white p-4">
                  <dt className="text-xs uppercase tracking-wide text-zinc-500">Model</dt>
                  <dd className="mt-1 break-words font-medium">{plan.modelId}</dd>
                </div>
              </dl>
              <div className="rounded-md border border-zinc-200 bg-white p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <BadgeDollarSign aria-hidden="true" className="h-4 w-4" />
                  Recommendation
                </div>
                <p className="mt-2 text-sm leading-6 text-zinc-600">{plan.recommendation.reason}</p>
              </div>
              <div className="rounded-md border border-zinc-200 bg-white p-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <AlertTriangle aria-hidden="true" className="h-4 w-4" />
                  Uncertainty
                </div>
                <p className="mt-2 text-sm leading-6 text-zinc-600">{plan.recommendation.uncertainty}</p>
              </div>
              <button
                className="inline-flex min-h-10 items-center gap-2 rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium"
                type="button"
              >
                <ShieldCheck aria-hidden="true" className="h-4 w-4" />
                Request approval
              </button>
            </div>
          ) : (
            <div className="mt-4 rounded-md border border-dashed border-zinc-300 bg-white p-5 text-sm text-zinc-600">
              Generate a plan to see provider choice, GPU estimate, uncertainty, and the approval gate.
            </div>
          )}
        </section>
      </div>
    </AppFrame>
  );
}
