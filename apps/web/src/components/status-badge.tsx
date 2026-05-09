import type { DeploymentStatus, HealthStatus, ProviderStatus } from "@crucible/shared/crucible-contract";

import { formatStatusLabel } from "@/lib/format";

type Status = DeploymentStatus | ProviderStatus | HealthStatus | "generated";

const toneByStatus: Record<string, string> = {
  approval_required: "border-amber-300 bg-amber-50 text-amber-800",
  approved: "border-sky-300 bg-sky-50 text-sky-800",
  configured: "border-slate-300 bg-slate-50 text-slate-700",
  draft: "border-slate-300 bg-slate-50 text-slate-700",
  dry_run_only: "border-blue-300 bg-blue-50 text-blue-800",
  failed: "border-red-300 bg-red-50 text-red-800",
  failing: "border-red-300 bg-red-50 text-red-800",
  generated: "border-zinc-300 bg-zinc-50 text-zinc-800",
  health_checking: "border-indigo-300 bg-indigo-50 text-indigo-800",
  live: "border-emerald-300 bg-emerald-50 text-emerald-800",
  not_run: "border-zinc-300 bg-zinc-50 text-zinc-700",
  passing: "border-emerald-300 bg-emerald-50 text-emerald-800",
  pending: "border-amber-300 bg-amber-50 text-amber-800",
  provisioning: "border-blue-300 bg-blue-50 text-blue-800",
  queued: "border-blue-300 bg-blue-50 text-blue-800",
  ready: "border-emerald-300 bg-emerald-50 text-emerald-800",
  stopped: "border-zinc-300 bg-zinc-50 text-zinc-700",
  stopping: "border-amber-300 bg-amber-50 text-amber-800",
  unsupported: "border-zinc-300 bg-zinc-50 text-zinc-700"
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
        toneByStatus[status] ?? "border-zinc-300 bg-zinc-50 text-zinc-700"
      }`}
    >
      {children ?? formatStatusLabel(status)}
    </span>
  );
}
