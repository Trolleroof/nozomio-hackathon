"use client";

import { LoaderCircle, ServerCog } from "lucide-react";
import { useEffect, useState } from "react";

import { formatCurrency } from "@/lib/format";
import {
  objectiveLabel,
  readOnboardingLaunch,
  type OnboardingLaunch
} from "@/lib/onboarding-launch";

import { StatusBadge } from "./status-badge";

export function OnboardingLiveDeployment() {
  const [launch, setLaunch] = useState<OnboardingLaunch | null>(null);

  useEffect(() => {
    setLaunch(readOnboardingLaunch(window.localStorage));
  }, []);

  if (!launch) {
    return null;
  }

  return (
    <section className="mb-5 rounded-lg border border-accent/40 bg-accent/10 p-5 text-foreground">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="flex items-center gap-2">
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin text-accent" />
            <h2 className="text-lg font-semibold tracking-tight">Live first model launch</h2>
          </div>
          <p className="mt-2 break-words text-sm leading-6 text-muted-foreground">{launch.modelId}</p>
        </div>
        <StatusBadge status={launch.status} />
      </div>

      <div className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
        <div className="rounded-md border border-border bg-background/50 p-3">
          <div className="text-muted-foreground">Route</div>
          <div className="mt-1 font-medium">{launch.provider} · {launch.accelerator}</div>
        </div>
        <div className="rounded-md border border-border bg-background/50 p-3">
          <div className="text-muted-foreground">Objective</div>
          <div className="mt-1 font-medium">Optimizing for {objectiveLabel(launch.objective)}</div>
        </div>
        <div className="rounded-md border border-border bg-background/50 p-3">
          <div className="text-muted-foreground">Estimate</div>
          <div className="mt-1 font-medium">{formatCurrency(launch.estimatedHourlyUsd)}/hr</div>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
        <ServerCog aria-hidden="true" className="h-4 w-4 text-forge" />
        Provisioning worker is preparing the OpenAI-compatible endpoint.
      </div>
    </section>
  );
}
