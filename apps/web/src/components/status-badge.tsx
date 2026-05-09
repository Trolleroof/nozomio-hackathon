import type { DeploymentStatus, HealthStatus, ProviderStatus } from "@crucible/shared/crucible-contract";

import { formatStatusLabel } from "@/lib/format";

type Status = DeploymentStatus | ProviderStatus | HealthStatus | "generated";

const toneByStatus: Record<string, string> = {
  approval_required: "border-forge/60 bg-forge/15 text-forge",
  approved: "border-accent/55 bg-accent/15 text-accent-hover",
  configured: "border-border bg-surface-raised text-muted-foreground",
  draft: "border-border bg-surface-raised text-muted-foreground",
  dry_run_only: "border-accent/55 bg-accent/15 text-accent-hover",
  error: "border-ember/60 bg-ember/15 text-ember",
  failed: "border-ember/60 bg-ember/15 text-ember",
  failing: "border-ember/60 bg-ember/15 text-ember",
  generated: "border-border bg-surface-raised text-foreground",
  health_checking: "border-accent/55 bg-accent/15 text-accent-hover",
  info: "border-border bg-surface-raised text-muted-foreground",
  live: "border-success/60 bg-success/15 text-success",
  not_run: "border-border bg-surface-raised text-muted-foreground",
  passing: "border-success/60 bg-success/15 text-success",
  pending: "border-forge/60 bg-forge/15 text-forge",
  provisioning: "border-accent/55 bg-accent/15 text-accent-hover",
  queued: "border-accent/55 bg-accent/15 text-accent-hover",
  ready: "border-success/60 bg-success/15 text-success",
  stopped: "border-border bg-surface-raised text-muted-foreground",
  stopping: "border-forge/60 bg-forge/15 text-forge",
  unsupported: "border-border bg-surface-raised text-muted-foreground",
  warn: "border-forge/60 bg-forge/15 text-forge"
};

export function StatusBadge({
  status,
  children
}: {
  status: Status | string;
  children?: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${
        toneByStatus[status] ?? "border-border bg-surface-raised text-muted-foreground"
      }`}
    >
      {children ?? formatStatusLabel(status)}
    </span>
  );
}
