import { TerminalSquare } from "lucide-react";

import { AppFrame } from "@/components/app-frame";
import { DeploymentTimeline } from "@/components/deployment-timeline";
import { LogPanel } from "@/components/log-panel";
import { PlaygroundPanel } from "@/components/playground-panel";
import { StatusBadge } from "@/components/status-badge";
import { formatDateTime, formatLatency } from "@/lib/format";
import { deployments } from "@crucible/shared/fixtures";

export default function DeploymentDetailPage() {
  const deployment = deployments.find((item) => item.id === "dep_qwen_modal") ?? deployments[0];

  return (
    <AppFrame>
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <h1 className="text-2xl font-medium tracking-tight">{deployment.name}</h1>
          <p className="mt-2 text-sm text-muted-foreground">Updated {formatDateTime(deployment.updatedAt)}</p>
        </div>
        <StatusBadge status={deployment.status} />
      </div>

      <div className="space-y-5">
        <DeploymentTimeline status={deployment.status} />

        <section className="crucible-card">
          <h2 className="text-lg font-semibold tracking-tight">Endpoint</h2>
          <p className="mt-2 break-all text-sm text-muted-foreground">{deployment.endpointUrl ?? "Endpoint is not available yet."}</p>
          <pre className="crucible-code mt-4 overflow-x-auto"><code>{`curl ${deployment.endpointUrl ?? "https://deployment.example/v1"}/models \\
  -H "Authorization: Bearer $CRUCIBLE_API_TOKEN"`}</code></pre>
        </section>

        <section className="crucible-card">
          <h2 className="text-lg font-semibold tracking-tight">Health checks</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {deployment.healthChecks.map((check) => (
              <div key={check.id} className="crucible-card-compact">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{check.name}</span>
                  <StatusBadge status={check.status} />
                </div>
                <div className="mt-3 text-sm text-muted-foreground">
                  {formatLatency(check.latencyMs)} · {formatDateTime(check.checkedAt)}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="crucible-card">
          <h2 className="text-lg font-semibold tracking-tight">Benchmark</h2>
          {deployment.benchmark ? (
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Prompt tokens</th>
                    <th className="py-2 pr-4 font-medium">Completion tokens</th>
                    <th className="py-2 pr-4 font-medium">Latency</th>
                    <th className="py-2 pr-4 font-medium">Tokens/sec</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="py-3 pr-4">{deployment.benchmark.promptTokens}</td>
                    <td className="py-3 pr-4">{deployment.benchmark.completionTokens}</td>
                    <td className="py-3 pr-4">{deployment.benchmark.latencyMs} ms</td>
                    <td className="py-3 pr-4">{deployment.benchmark.tokensPerSecond}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">Benchmark runs after the endpoint passes health checks.</p>
          )}
        </section>

        <section className="crucible-card">
          <h2 className="text-lg font-semibold tracking-tight">Why the agent chose this path</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {deployment.context.map((snippet) => (
              <div key={snippet.id} className="crucible-card-compact">
                <div className="font-medium">{snippet.title}</div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{snippet.usedFor}</p>
              </div>
            ))}
          </div>
        </section>

        <LogPanel logs={deployment.logs} />
        <PlaygroundPanel deployment={deployment} />

        <section className="crucible-card">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Controls</h2>
              <p className="mt-1 text-sm text-muted-foreground">Stop is shown for the contract, but fixtures do not call a provider.</p>
            </div>
            <button
              className="crucible-danger min-h-10 gap-2"
              type="button"
            >
              <TerminalSquare aria-hidden="true" className="h-4 w-4" />
              Stop deployment
            </button>
          </div>
        </section>
      </div>
    </AppFrame>
  );
}
