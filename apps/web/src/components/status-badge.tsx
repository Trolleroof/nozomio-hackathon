import type { DeploymentStatus, HealthStatus, ProviderStatus } from "@crucible/shared/crucible-contract";

import { formatStatusLabel } from "@/lib/format";

type Status = DeploymentStatus | ProviderStatus | HealthStatus | "generated";

const toneByStatus: Record<string, string> = {
  approval_required: "text-forge",
  approved: "text-accent-hover",
  configured: "text-muted-foreground",
  draft: "text-muted-foreground",
  dry_run_only: "text-accent-hover",
  error: "text-ember",
  failed: "text-ember",
  failing: "text-ember",
  generated: "text-foreground",
  health_checking: "text-accent-hover",
  info: "text-muted-foreground",
  live: "text-success",
  not_run: "text-muted-foreground",
  passing: "text-success",
  pending: "text-forge",
  provisioning: "text-accent-hover",
  queued: "text-accent-hover",
  ready: "text-success",
  stopped: "text-muted-foreground",
  stopping: "text-forge",
  unsupported: "text-muted-foreground",
  warn: "text-forge"
};

export function StatusBadge({
  status,
  children
}: {
  status: Status | string;
  children?: React.ReactNode;
}) {
  const label = children ?? formatStatusLabel(status);

  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.08em] ${
        toneByStatus[status] ?? "text-muted-foreground"
      }`}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 bg-current" />
      {label}
    </span>
  );
}
