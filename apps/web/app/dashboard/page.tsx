import { ArrowRight, BookOpenText, BrainCircuit, Rocket, ServerCog } from "lucide-react";
import Link from "next/link";

import { AppFrame } from "@/components/app-frame";
import { EndpointConsole } from "@/components/endpoint-console";
import { OnboardingLiveDeployment } from "@/components/onboarding-live-deployment";
import { StatusBadge } from "@/components/status-badge";
import { listContextSnippets, listDeployments, listProviderCapabilities } from "@/lib/crucible-data";
import { listMcpActivity } from "@/lib/crucible-mcp-activity";

export default async function DashboardPage() {
  const [deployments, providerCapabilities, contextSnippets, mcpActivity] = await Promise.all([
    listDeployments(),
    listProviderCapabilities(),
    listContextSnippets(),
    listMcpActivity()
  ]);
  const readyCount = deployments.filter((deployment) => deployment.status === "ready").length;
  const liveProviders = providerCapabilities.filter((provider) => provider.status === "live").length;
  const runningRunCount = mcpActivity.runCapsules.filter((run) => run.status === "running").length;

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

      <OnboardingLiveDeployment />

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
              <span className="text-sm text-muted-foreground">{mcpActivity.deployments.length} events</span>
            </div>
            {mcpActivity.deployments.length ? (
              <div className="mt-4 divide-y divide-border">
                {mcpActivity.deployments.slice(0, 5).map((deployment) => (
                  <div key={deployment.id} className="grid gap-2 py-3 text-sm sm:grid-cols-[1fr_7rem_8rem]">
                    <span>
                      <span className="font-medium text-foreground">{deployment.id}</span>
                      <span className="mt-1 block break-all text-muted-foreground">{deployment.endpointUrl}</span>
                    </span>
                    <span className="text-muted-foreground">{deployment.provider}</span>
                    <span className="sm:justify-self-end">
                      <StatusBadge status={deployment.status} />
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                No deployment or test run history yet. Launch a deployment or record a run to populate this feed.
              </p>
            )}
          </section>

          <section className="crucible-card">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <BrainCircuit aria-hidden="true" className="h-4 w-4 text-forge" />
                <h2 className="text-lg font-semibold tracking-tight">RL and training runs</h2>
              </div>
              <span className="text-sm text-muted-foreground">{runningRunCount} running</span>
            </div>
            {mcpActivity.runCapsules.length ? (
              <div className="mt-4 divide-y divide-border">
                {mcpActivity.runCapsules.slice(0, 5).map((run) => (
                  <div key={run.id} className="grid gap-2 py-3 text-sm sm:grid-cols-[1fr_7rem_8rem]">
                    <span>
                      <span className="font-medium text-foreground">{run.prompt}</span>
                      <span className="mt-1 block text-muted-foreground">
                        {run.sourceAgent} · {run.phase ?? "approval gate"} · {run.gpuName ?? run.provider ?? "provider pending"}
                      </span>
                    </span>
                    <span className="text-muted-foreground">
                      {run.successRate === undefined ? "pending" : `${Math.round(run.successRate * 100)}% success`}
                    </span>
                    <span className="sm:justify-self-end">
                      <StatusBadge status={run.status} />
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                No RL or training runs yet. Approved run capsules and training events will appear here once recorded.
              </p>
            )}
            {mcpActivity.errors.length ? (
              <p className="mt-3 text-xs text-ember">{mcpActivity.errors[0]}</p>
            ) : null}
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
