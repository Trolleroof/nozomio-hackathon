import { ArrowRight, BookOpenText, Rocket, ServerCog } from "lucide-react";
import Link from "next/link";

import { AppFrame } from "@/components/app-frame";
import { StatusBadge } from "@/components/status-badge";
import { formatDateTime } from "@/lib/format";
import { contextSnippets, deployments, generatedPlan, providerCapabilities } from "@crucible/shared/fixtures";

export default function DashboardPage() {
  const readyCount = deployments.filter((deployment) => deployment.status === "ready").length;
  const liveProviders = providerCapabilities.filter((provider) => provider.status === "live").length;

  return (
    <AppFrame>
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-medium tracking-tight">Dashboard</h1>
        </div>
        <Link
          href="/deployments/new"
          className="crucible-primary min-h-10 gap-2"
        >
          <Rocket aria-hidden="true" className="h-4 w-4" />
          New deployment
        </Link>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <section className="crucible-card md:col-span-2">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold tracking-tight">Active deployments</h2>
            <span className="text-sm text-muted-foreground">{readyCount} healthy</span>
          </div>
          <div className="mt-4 divide-y divide-border">
            {deployments.slice(0, 4).map((deployment) => (
              <Link
                key={deployment.id}
                href={`/deployments/${deployment.id}`}
                className="grid gap-2 rounded-md py-3 text-sm hover:bg-surface-raised sm:grid-cols-[1fr_auto_auto]"
              >
                <span>
                  <span className="font-medium text-foreground">{deployment.name}</span>
                  <span className="mt-1 block text-muted-foreground">{deployment.modelId}</span>
                </span>
                <span className="text-muted-foreground">{deployment.provider}</span>
                <StatusBadge status={deployment.status} />
              </Link>
            ))}
          </div>
        </section>

        <section className="crucible-card">
          <div className="flex items-center gap-2">
            <ServerCog aria-hidden="true" className="h-4 w-4 text-accent" />
            <h2 className="text-lg font-semibold tracking-tight">Provider status</h2>
          </div>
          <p className="mt-4 text-3xl font-semibold">{liveProviders}</p>
          <p className="mt-1 text-sm text-muted-foreground">live provider, with dry-run and configured providers clearly labeled.</p>
          <Link className="crucible-link mt-4 inline-flex items-center gap-1" href="/providers">
            View providers <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </section>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <section className="crucible-card">
          <h2 className="text-lg font-semibold tracking-tight">Quick deployment</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{generatedPlan.prompt}</p>
          <Link className="crucible-link mt-4 inline-flex items-center gap-1" href="/deployments/new">
            Generate plan <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </section>

        <section className="crucible-card">
          <h2 className="text-lg font-semibold tracking-tight">Recent plans</h2>
          <p className="mt-2 text-sm text-muted-foreground">{generatedPlan.modelId}</p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <StatusBadge status={generatedPlan.status}>Generated</StatusBadge>
            <span className="text-sm text-muted-foreground">{formatDateTime(generatedPlan.createdAt)}</span>
          </div>
        </section>

        <section className="crucible-card">
          <div className="flex items-center gap-2">
            <BookOpenText aria-hidden="true" className="h-4 w-4 text-forge" />
            <h2 className="text-lg font-semibold tracking-tight">Context used by agent</h2>
          </div>
          <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
            {contextSnippets.slice(0, 3).map((snippet) => (
              <li key={snippet.id}>{snippet.title}</li>
            ))}
          </ul>
          <Link className="crucible-link mt-4 inline-flex items-center gap-1" href="/context">
            Open context <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
        </section>
      </div>
    </AppFrame>
  );
}
