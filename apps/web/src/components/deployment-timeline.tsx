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
    <ol className="flex flex-wrap gap-x-6 gap-y-3 border-b border-border pb-4">
      {steps.map((step) => {
        const Icon = step.icon;
        const isCurrent = step.status === status;
        return (
          <li
            key={step.status}
            className={`flex items-center gap-2 transition-colors duration-200 ${
              isCurrent ? "text-accent" : "text-muted-foreground"
            }`}
          >
            <Icon
              aria-hidden="true"
              className={`h-4 w-4 ${
                step.status === "provisioning" && isCurrent
                  ? "animate-spin"
                  : step.status === "health_checking" && isCurrent
                    ? "crucible-status-pulse"
                    : ""
              }`}
            />
            <span className="text-sm font-medium">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
