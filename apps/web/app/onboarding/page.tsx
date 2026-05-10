"use client";

import type { DeploymentObjective } from "@crucible/shared/crucible-contract";
import { Activity, ArrowRight, Gauge, ShieldCheck, WalletCards, Zap } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { BrandMark } from "@/components/brand-mark";
import { generateDeploymentPlan } from "@/lib/crucible-client";
import {
  createOnboardingLaunch,
  onboardingCompleteStorageKey,
  onboardingLaunchStorageKey
} from "@/lib/onboarding-launch";

const modelOptions = [
  {
    id: "Qwen/Qwen2.5-0.5B-Instruct",
    name: "Qwen 0.5B Instruct",
    summary: "Fast smoke-test model for checking the full endpoint path.",
    fit: "Lowest cold-start risk"
  },
  {
    id: "Qwen/Qwen2.5-7B-Instruct",
    name: "Qwen 7B Instruct",
    summary: "A practical first production-style assistant model.",
    fit: "Balanced default"
  },
  {
    id: "mistralai/Mistral-7B-Instruct-v0.3",
    name: "Mistral 7B Instruct",
    summary: "Good general-purpose instruction model with broad runtime support.",
    fit: "Reliable routing"
  },
  {
    id: "meta-llama/Meta-Llama-3.1-8B-Instruct",
    name: "Llama 3.1 8B Instruct",
    summary: "A stronger chat model when quality matters more than minimum cost.",
    fit: "Higher capability"
  }
];

const objectiveOptions: {
  value: DeploymentObjective;
  label: string;
  description: string;
  icon: typeof WalletCards;
}[] = [
  {
    value: "cheapest",
    label: "Price",
    description: "Prefer the lowest viable hourly GPU route.",
    icon: WalletCards
  },
  {
    value: "low_latency",
    label: "Latency",
    description: "Prefer faster response and cold-start behavior.",
    icon: Zap
  },
  {
    value: "reliable",
    label: "Reliability",
    description: "Prefer the safest live provider and accelerator.",
    icon: ShieldCheck
  }
];

export default function OnboardingPage() {
  const router = useRouter();
  const [modelId, setModelId] = useState(modelOptions[1].id);
  const [objective, setObjective] = useState<DeploymentObjective>("cheapest");
  const [status, setStatus] = useState<"idle" | "launching">("idle");
  const [error, setError] = useState<string | null>(null);

  const selectedModel = modelOptions.find((model) => model.id === modelId) ?? modelOptions[0];
  const selectedObjective = objectiveOptions.find((item) => item.value === objective) ?? objectiveOptions[0];

  async function handleLaunch() {
    setStatus("launching");
    setError(null);
    try {
      const plan = await generateDeploymentPlan({
        prompt: `Spin up ${selectedModel.name} optimized for ${selectedObjective.label.toLowerCase()}.`,
        modelId: selectedModel.id,
        objective,
        stopPolicy: "demo_window"
      });
      const launch = createOnboardingLaunch(plan, selectedModel.name);
      localStorage.setItem(onboardingLaunchStorageKey, JSON.stringify(launch));
      localStorage.setItem(onboardingCompleteStorageKey, "true");
      router.push("/dashboard");
      if (process.env.NODE_ENV !== "test") {
        window.location.assign("/dashboard");
      }
    } catch (launchError) {
      setError(launchError instanceof Error ? launchError.message : "Launch failed.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <main className="crucible-shell">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-6 py-6">
        <header className="flex items-center justify-between">
          <Link href="/" className="inline-flex items-center" aria-label="Crucible Compute">
            <BrandMark />
          </Link>
          <Link href="/dashboard" className="crucible-secondary min-h-9 px-3">
            Skip
          </Link>
        </header>

        <section className="grid flex-1 items-center gap-8 py-10 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="max-w-md">
            <div className="flex h-11 w-11 items-center justify-center rounded-md border border-border bg-surface-raised text-accent">
              <Activity aria-hidden="true" className="h-5 w-5" />
            </div>
            <h1 className="mt-6 text-3xl font-semibold tracking-tight sm:text-4xl">
              Choose your first model
            </h1>
            <p className="mt-4 text-sm leading-6 text-muted-foreground">
              Pick a model and what Crucible should optimize for. The next step generates a live plan,
              starts the spin-up state, and lands you on the operational dashboard.
            </p>
            <div className="mt-6 rounded-md border border-border bg-muted p-4 text-sm leading-6 text-muted-foreground">
              <div className="flex items-center gap-2 text-foreground">
                <Gauge aria-hidden="true" className="h-4 w-4 text-forge" />
                First run uses the live provider path when available.
              </div>
            </div>
          </div>

          <div className="space-y-5">
            <section className="crucible-card">
              <h2 className="text-lg font-semibold tracking-tight">Model</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {modelOptions.map((model) => (
                  <label
                    key={model.id}
                    className={`block cursor-pointer rounded-md border p-4 transition-colors ${
                      modelId === model.id
                        ? "border-accent bg-accent/10"
                        : "border-border bg-surface-raised hover:border-border-strong"
                    }`}
                  >
                    <input
                      className="sr-only"
                      type="radio"
                      name="model"
                      checked={modelId === model.id}
                      onChange={() => setModelId(model.id)}
                    />
                    <span className="block text-sm font-medium">{model.name}</span>
                    <span className="mt-2 block text-sm leading-6 text-muted-foreground">{model.summary}</span>
                    <span className="mt-3 block font-mono text-xs text-forge">{model.fit}</span>
                  </label>
                ))}
              </div>
            </section>

            <section className="crucible-card">
              <h2 className="text-lg font-semibold tracking-tight">Optimize for</h2>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {objectiveOptions.map((item) => {
                  const Icon = item.icon;
                  return (
                    <label
                      key={item.value}
                      className={`block cursor-pointer rounded-md border p-4 transition-colors ${
                        objective === item.value
                          ? "border-accent bg-accent/10"
                          : "border-border bg-surface-raised hover:border-border-strong"
                      }`}
                    >
                      <input
                        className="sr-only"
                        type="radio"
                        name="objective"
                        checked={objective === item.value}
                        onChange={() => setObjective(item.value)}
                      />
                      <span className="flex items-center gap-2 text-sm font-medium">
                        <Icon aria-hidden="true" className="h-4 w-4 text-accent" />
                        {item.label}
                      </span>
                      <span className="mt-2 block text-sm leading-6 text-muted-foreground">{item.description}</span>
                    </label>
                  );
                })}
              </div>
            </section>

            {error ? (
              <div className="rounded-md border border-ember/40 bg-ember/10 p-3 text-sm text-ember">
                {error}
              </div>
            ) : null}

            <button
              type="button"
              className="crucible-primary min-h-11 w-full gap-2 px-5 sm:w-auto"
              onClick={handleLaunch}
              disabled={status === "launching"}
            >
              {status === "launching" ? "Launching model" : "Launch model"}
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </button>
          </div>
        </section>
      </div>
    </main>
  );
}
