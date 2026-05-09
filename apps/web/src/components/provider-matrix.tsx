import type { ProviderCapability } from "@crucible/shared/crucible-contract";
import { AlertTriangle, Check, Minus } from "lucide-react";

import { StatusBadge } from "@/components/status-badge";
import { formatDateTime } from "@/lib/format";

function capabilityLabel(provider: ProviderCapability) {
  if (provider.status === "live") {
    return "Live";
  }

  if (provider.status === "dry_run_only") {
    return "Dry run";
  }

  if (provider.status === "configured") {
    return "Configured";
  }

  if (provider.status === "failed") {
    return "Failed";
  }

  return "Blocked";
}

function CapabilityMark({ enabled }: { enabled: boolean }) {
  return enabled ? (
    <Check aria-label="supported" className="h-4 w-4 text-success" />
  ) : (
    <Minus aria-label="not supported" className="h-4 w-4 text-muted-foreground" />
  );
}

export function ProviderMatrix({ providers }: { providers: ProviderCapability[] }) {
  return (
    <section className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="crucible-card-compact text-sm font-medium">
          Live deploy supported
        </div>
        <div className="crucible-card-compact text-sm font-medium">
          Dry-run/planning supported
        </div>
        <div className="crucible-card-compact text-sm font-medium">
          Configured but not tested
        </div>
        <div className="crucible-card-compact text-sm font-medium">
          Unsupported
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-border bg-surface">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-muted text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Provider</th>
                <th className="px-4 py-3 font-medium">Adapter</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Endpoint</th>
                <th className="px-4 py-3 font-medium">Logs</th>
                <th className="px-4 py-3 font-medium">Stop</th>
                <th className="px-4 py-3 font-medium">Checked</th>
                <th className="px-4 py-3 font-medium">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {providers.map((provider) => (
                <tr key={provider.id} className="align-top">
                  <td className="px-4 py-4 font-medium text-foreground">{provider.provider}</td>
                  <td className="px-4 py-4 text-muted-foreground">{provider.adapter}</td>
                  <td className="px-4 py-4">
                    <StatusBadge status={provider.status}>{capabilityLabel(provider)}</StatusBadge>
                  </td>
                  <td className="px-4 py-4">
                    <CapabilityMark enabled={provider.supportsOpenAIEndpoint} />
                  </td>
                  <td className="px-4 py-4">
                    <CapabilityMark enabled={provider.supportsLogs} />
                  </td>
                  <td className="px-4 py-4">
                    <CapabilityMark enabled={provider.supportsStop} />
                  </td>
                  <td className="px-4 py-4 font-mono text-muted-foreground">{formatDateTime(provider.lastCheckedAt)}</td>
                  <td className="max-w-xs px-4 py-4 text-muted-foreground">
                    <div>{provider.notes}</div>
                    {provider.lastError ? (
                      <div className="mt-2 flex gap-2 text-ember">
                        <AlertTriangle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
                        <span>{provider.lastError}</span>
                      </div>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
