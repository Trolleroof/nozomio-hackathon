import type { Deployment, TrainingRun } from "@crucible/shared/crucible-contract";
import { Activity, ArrowRight, BookOpenText, BrainCircuit, FlaskConical, Rocket, ServerCog } from "lucide-react";
import Link from "next/link";

import { AppFrame } from "@/components/app-frame";
import { EndpointConsole } from "@/components/endpoint-console";
import { StatusBadge } from "@/components/status-badge";
import { listContextSnippets, listDeployments, listProviderCapabilities, listTrainingRuns } from "@/lib/crucible-data";
import { formatCurrency, formatDateTime } from "@/lib/format";

export default async function DashboardPage() {
  const [deployments, providerCapabilities, contextSnippets] = await Promise.all([
    listDeployments(),
    listProviderCapabilities(),
    listContextSnippets()
  ]);
  const trainingRuns = await listTrainingRuns();
  const readyCount = deployments.filter((deployment) => deployment.status === "ready").length;
  const liveProviders = providerCapabilities.filter((provider) => provider.status === "live").length;
  const runningTrainingRuns = trainingRuns.filter((run) => run.status === "running").length;
  const historyItems = deploymentHistoryItems(deployments, trainingRuns);

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

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="space-y-5">
          <section className="crucible-card">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-lg font-semibold tracking-tight">Active deployments</h2>
              <span className="text-sm text-muted-foreground">{readyCount} healthy</span>
            </div>
            {deployments.length ? (
              <div className="mt-4 divide-y divide-border">
                {deployments.slice(0, 4).map((deployment) => (
                  <Link
                    key={deployment.id}
                    href={`/deployments/${deployment.id}`}
                    className="grid gap-2 py-3 text-sm transition-colors hover:text-accent sm:grid-cols-[1fr_7rem_9rem]"
                  >
                    <span>
                      <span className="font-medium text-foreground">{deployment.name}</span>
                      <span className="mt-1 block text-muted-foreground">{deployment.modelId}</span>
                    </span>
                    <span className="text-muted-foreground">{deployment.provider}</span>
                    <span className="sm:justify-self-end">
                      <StatusBadge status={deployment.status} />
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                No live deployments found. Start the AnyGPU gateway or deploy a real model to populate this list.
              </p>
            )}
          </section>

          <section className="crucible-card">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-lg font-semibold tracking-tight">Deployment history</h2>
              <span className="text-sm text-muted-foreground">{historyItems.length} events</span>
            </div>
            {historyItems.length ? (
              <div className="mt-4 divide-y divide-border">
                {historyItems.slice(0, 6).map((item) => (
                  <HistoryRow key={item.id} item={item} />
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                No deployment or test run history yet. Launch a deployment or record a run to populate this feed.
              </p>
            )}
          </section>

          <section className="crucible-card">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <BrainCircuit aria-hidden="true" className="h-4 w-4 text-forge" />
                <h2 className="text-lg font-semibold tracking-tight">RL and training runs</h2>
              </div>
              <span className="text-sm text-muted-foreground">{runningTrainingRuns} running</span>
            </div>
            {trainingRuns.length ? (
              <div className="mt-4 space-y-3">
                {trainingRuns.slice(0, 4).map((run) => (
                  <TrainingRunRow key={run.id} run={run} />
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                No RL or training runs yet. Approved run capsules and training events will appear here once recorded.
              </p>
            )}
          </section>

          <EndpointConsole deployments={deployments} />
        </div>

        <div className="space-y-5">
          <section className="crucible-card">
            <h2 className="text-lg font-semibold tracking-tight">Quick deployment</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Generate a plan from your own model, objective, and current provider configuration.
            </p>
            <Link className="crucible-link mt-4 inline-flex items-center gap-1" href="/deployments/new">
              Generate plan <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
          </section>

          <section className="crucible-card">
            <div className="flex items-center gap-2">
              <ServerCog aria-hidden="true" className="h-4 w-4 text-accent" />
              <h2 className="text-lg font-semibold tracking-tight">Provider status</h2>
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              {liveProviders} live provider. Dry-run and configured providers are labeled.
            </p>
            <Link className="crucible-link mt-4 inline-flex items-center gap-1" href="/providers">
              View providers <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
          </section>

          <section className="crucible-card">
            <div className="flex items-center gap-2">
              <BookOpenText aria-hidden="true" className="h-4 w-4 text-forge" />
              <h2 className="text-lg font-semibold tracking-tight">Context used by agent</h2>
            </div>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              {contextSnippets.length ? (
                contextSnippets.slice(0, 3).map((snippet) => (
                  <li key={snippet.id}>{snippet.title}</li>
                ))
              ) : (
                <li>No live context yet.</li>
              )}
            </ul>
            <Link className="crucible-link mt-4 inline-flex items-center gap-1" href="/context">
              Open context <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
          </section>
        </div>
      </div>
    </AppFrame>
  );
}

type DeploymentHistoryItem = {
  id: string;
  title: string;
  subtitle: string;
  timestamp: string;
  status: Deployment["status"] | TrainingRun["status"];
  href?: string;
  type: "deployment" | "test_run";
};

function deploymentHistoryItems(deployments: Deployment[], trainingRuns: TrainingRun[]): DeploymentHistoryItem[] {
  return [
    ...deployments.map((deployment) => ({
      id: `deployment_${deployment.id}`,
      title: deployment.name,
      subtitle: `${deployment.provider} / ${deployment.modelId}`,
      timestamp: deployment.updatedAt,
      status: deployment.status,
      href: `/deployments/${deployment.id}`,
      type: "deployment" as const
    })),
    ...trainingRuns.map((run) => ({
      id: `test_run_${run.id}`,
      title: run.name,
      subtitle: testRunSubtitle(run),
      timestamp: run.updatedAt,
      status: run.status,
      type: "test_run" as const
    }))
  ].sort((left, right) => right.timestamp.localeCompare(left.timestamp));
}

function HistoryRow({ item }: { item: DeploymentHistoryItem }) {
  const content = (
    <div className="grid gap-3 py-3 text-sm sm:grid-cols-[1fr_8rem_9rem] sm:items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          {item.type === "test_run" ? (
            <FlaskConical aria-hidden="true" className="h-4 w-4 shrink-0 text-forge" />
          ) : (
            <Rocket aria-hidden="true" className="h-4 w-4 shrink-0 text-accent" />
          )}
          <span className="font-medium text-foreground">{item.title}</span>
        </div>
        <div className="mt-1 text-muted-foreground">{item.subtitle}</div>
      </div>
      <span className="text-muted-foreground">{formatDateTime(item.timestamp)}</span>
      <span className="sm:justify-self-end">
        <StatusBadge status={item.status} />
      </span>
    </div>
  );

  if (item.href) {
    return (
      <Link href={item.href} className="block transition-colors hover:text-accent">
        {content}
      </Link>
    );
  }

  return content;
}

function testRunSubtitle(run: TrainingRun) {
  const providerLabel = run.gpuName ? `${run.provider} / ${run.gpuName}` : run.provider;
  return `Test run · ${providerLabel} · ${run.phase}`;
}

function TrainingRunRow({ run }: { run: TrainingRun }) {
  const providerLabel = run.gpuName ? `${run.provider} / ${run.gpuName}` : run.provider;
  return (
    <div className="rounded-md border border-border bg-surface-raised p-4 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-foreground">{run.name}</span>
            <span className="crucible-code px-2 py-1 text-[11px] uppercase tracking-[0.08em] text-muted-foreground">
              {run.kind}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
            <span>{providerLabel}</span>
            <span>{run.phase}</span>
          </div>
        </div>
        <StatusBadge status={run.status} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-4">
        <Metric label="success" value={formatPercent(run.successRate)} />
        <Metric label="reward" value={formatReward(run.rewardMean)} />
        <Metric label="rollouts" value={formatRollouts(run.rolloutCount)} />
        <Metric label="cost" value={formatCost(run.costBurnUsd)} />
      </div>

      {run.latestEvent ? (
        <div className="mt-3 flex gap-2 text-sm text-muted-foreground">
          <Activity aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
          <span>{run.latestEvent}</span>
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.08em] text-muted-foreground">{label}</div>
      <div className="mt-1 font-medium text-foreground">{value}</div>
    </div>
  );
}

function formatPercent(value?: number) {
  if (typeof value !== "number") {
    return "pending";
  }
  return `success ${Math.round(value * 100)}%`;
}

function formatReward(value?: number) {
  if (typeof value !== "number") {
    return "reward pending";
  }
  return `reward ${value.toFixed(2)}`;
}

function formatRollouts(value?: number) {
  if (typeof value !== "number") {
    return "rollouts pending";
  }
  return `${value} rollouts`;
}

function formatCost(value?: number) {
  if (typeof value !== "number") {
    return "cost pending";
  }
  if (value > 0 && value < 0.01) {
    return `cost $${(Math.round(value * 10000) / 10000).toFixed(4)}`;
  }
  return `cost ${formatCurrency(value)}`;
}
