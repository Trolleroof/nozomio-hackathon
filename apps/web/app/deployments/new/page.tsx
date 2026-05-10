"use client";

import type { DeploymentObjective, DeploymentPlan } from "@crucible/shared/crucible-contract";
import { Cpu, Rocket } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppFrame } from "@/components/app-frame";
import { StatusBadge } from "@/components/status-badge";
import { deployDeploymentPlan, generateDeploymentPlan } from "@/lib/crucible-client";
import { formatCurrency } from "@/lib/format";

const modelOptions = [
  { value: "Qwen/Qwen2.5-7B-Instruct", label: "Qwen 2.5 7B Instruct" },
  { value: "mistralai/Mistral-7B-Instruct-v0.3", label: "Mistral 7B Instruct" },
  { value: "meta-llama/Llama-3.1-8B-Instruct", label: "Llama 3.1 8B Instruct" }
];
const objectives: { value: DeploymentObjective; label: string }[] = [
  { value: "cheapest", label: "Cheapest" },
  { value: "reliable", label: "Most reliable" },
  { value: "low_latency", label: "Lowest latency" }
];

export default function NewDeploymentPage() {
  const router = useRouter();
  const [initialParams] = useState(readInitialDeploymentParams);
  const [modelId, setModelId] = useState(initialParams.modelOption ?? modelOptions[0].value);
  const [customModel, setCustomModel] = useState(initialParams.customModel ?? "");
  const [objective, setObjective] = useState<DeploymentObjective>(initialParams.objective ?? "cheapest");
  const [notes, setNotes] = useState("");
  const [plan, setPlan] = useState<DeploymentPlan | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDeploying, setIsDeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resolvedModelId = normalizeHuggingFaceModel(customModel) || modelId;

  async function handleGenerate() {
    setIsGenerating(true);
    setError(null);
    try {
      const nextPlan = await generateDeploymentPlan({
        modelId: resolvedModelId,
        objective,
        notes: notes.trim()
      });
      setPlan(nextPlan);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Plan generation failed.");
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleDeploy() {
    if (!plan) {
      return;
    }
    setIsDeploying(true);
    setError(null);
    try {
      const deployment = await deployDeploymentPlan(plan);
      router.push(`/deployments/${deployment.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Deployment failed.");
      setIsDeploying(false);
    }
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
              <label className="block text-sm font-medium" htmlFor="model-select">
                Model
              </label>
              <select
                id="model-select"
                className="crucible-input mt-2 min-h-11 w-full"
                value={modelId}
                onChange={(event) => setModelId(event.target.value)}
              >
                {modelOptions.map((model) => (
                  <option key={model.value} value={model.value}>
                    {model.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium" htmlFor="model-link">
                Hugging Face link or model ID
              </label>
              <input
                id="model-link"
                className="crucible-input mt-2 min-h-11 w-full"
                placeholder="https://huggingface.co/org/model"
                value={customModel}
                onChange={(event) => setCustomModel(event.target.value)}
              />
            </div>
            <div>
              <div className="text-sm font-medium">Objective</div>
              <div className="mt-2 grid gap-2 sm:grid-cols-3">
                {objectives.map((item) => (
                  <label
                    key={item.value}
                    className={`flex min-h-12 items-center justify-center rounded-md border px-3 py-2 text-center text-sm font-medium transition ${
                      objective === item.value
                        ? "border-accent bg-accent/10 text-foreground"
                        : "border-border bg-muted/40 text-muted-foreground hover:border-border-strong"
                    }`}
                  >
                    <span className="flex items-start gap-3">
                      <input
                        aria-label={item.label}
                        className="mt-1 accent-accent"
                        type="radio"
                        name="objective"
                        value={item.value}
                        checked={objective === item.value}
                        onChange={() => setObjective(item.value)}
                      />
                      <span className="text-foreground">{item.label}</span>
                    </span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium" htmlFor="intent-notes">
                Optional notes
              </label>
              <textarea
                id="intent-notes"
                className="crucible-textarea mt-2 min-h-20 w-full"
                placeholder="Constraints, budget, provider preferences, launch window..."
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </div>
            <button
              className="crucible-primary min-h-11 gap-2 px-5"
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating || !resolvedModelId}
            >
              <Cpu aria-hidden="true" className={`h-4 w-4 ${isGenerating ? "animate-pulse" : ""}`} />
              {isGenerating ? "Generating plan" : "Generate plan"}
            </button>
          </div>
        </section>

        <section className="crucible-card-muted">
          <h2 className="text-lg font-semibold tracking-tight">Plan preview</h2>
          {isGenerating ? (
            <div
              aria-label="Deployment plan generation in progress"
              className="motion-fade-in mt-4 space-y-4"
              role="status"
            >
              <div className="max-w-md text-sm leading-6 text-muted-foreground">
                Generating plan with live NIA context and session memory.
              </div>
              <div className="space-y-2" aria-hidden="true">
                <div className="crucible-skeleton-line h-3 w-3/4 rounded bg-surface-raised" />
                <div className="crucible-skeleton-line h-3 w-1/2 rounded bg-surface-raised" />
                <div className="crucible-skeleton-line h-3 w-2/3 rounded bg-surface-raised" />
              </div>
            </div>
          ) : error ? (
            <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm leading-6 text-destructive">
              {error}
            </div>
          ) : plan ? (
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
              {plan.memoryInsights?.length ? (
                <div>
                  <h3 className="text-sm font-medium">Session memory</h3>
                  <div className="mt-2 space-y-2">
                    {plan.memoryInsights.map((insight) => (
                      <p key={insight} className="rounded-md border border-border bg-muted p-3 text-sm leading-6 text-muted-foreground">
                        {insight}
                      </p>
                    ))}
                  </div>
                </div>
              ) : null}
              <button
                className="crucible-primary min-h-11 gap-2 px-5"
                type="button"
                onClick={handleDeploy}
                disabled={isDeploying}
              >
                <Rocket aria-hidden="true" className={`h-4 w-4 ${isDeploying ? "animate-pulse" : ""}`} />
                {isDeploying ? "Deploying" : "Deploy"}
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

function normalizeHuggingFaceModel(value: string) {
  const raw = value.trim();
  if (!raw) {
    return "";
  }
  try {
    const url = new URL(raw);
    if (url.hostname === "huggingface.co" || url.hostname.endsWith(".huggingface.co")) {
      const [owner, model] = url.pathname.split("/").filter(Boolean);
      if (owner && model) {
        return `${owner}/${model}`;
      }
    }
  } catch {
    // Keep plain model IDs as entered.
  }
  return raw.replace(/^huggingface\.co\//, "").replace(/^https?:\/\/huggingface\.co\//, "");
}

function readInitialDeploymentParams() {
  if (typeof window === "undefined") {
    return {};
  }
  const params = new URLSearchParams(window.location.search);
  const requestedModel = normalizeHuggingFaceModel(params.get("modelId") ?? "");
  const knownModel = modelOptions.find((model) => model.value === requestedModel)?.value;
  const requestedObjective = params.get("objective");
  const objective = objectives.some((item) => item.value === requestedObjective)
    ? (requestedObjective as DeploymentObjective)
    : undefined;

  return {
    modelOption: knownModel,
    customModel: requestedModel && !knownModel ? requestedModel : undefined,
    objective
  };
}
