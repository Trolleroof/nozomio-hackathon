import type { DeploymentStatus } from "@crucible/shared/crucible-contract";
import {
  Activity,
  CheckCircle2,
  CircleX,
  LoaderCircle,
  ShieldCheck,
  Square
} from "lucide-react";

const steps = [
  { status: "approval_required", label: "Approval", icon: ShieldCheck },
  { status: "provisioning", label: "Provisioning", icon: LoaderCircle },
  { status: "health_checking", label: "Health check stage", icon: Activity },
  { status: "ready", label: "Ready", icon: CheckCircle2 },
  { status: "failed", label: "Failed", icon: CircleX },
  { status: "stopped", label: "Stopped", icon: Square }
] as const;

export function DeploymentTimeline({ status }: { status: DeploymentStatus }) {
  return (
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {steps.map((step) => {
        const Icon = step.icon;
        const isCurrent = step.status === status;
        return (
          <li
            key={step.status}
            className={`flex items-center gap-3 rounded-md border p-3 ${
              isCurrent
                ? "border-accent bg-accent text-accent-foreground"
                : "border-border bg-surface text-muted-foreground"
            }`}
          >
            <Icon aria-hidden="true" className={`h-4 w-4 ${step.status === "provisioning" && isCurrent ? "animate-spin" : ""}`} />
            <span className="text-sm font-medium">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
