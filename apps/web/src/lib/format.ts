import type { DeploymentStatus, HealthStatus, ProviderStatus } from "@crucible/shared/crucible-contract";

export function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2
  }).format(value);
}

export function formatDateTime(value?: string) {
  if (!value) {
    return "Not run";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  }).format(new Date(value));
}

export function formatLatency(value?: number) {
  if (typeof value !== "number") {
    return "Pending";
  }

  return `${value} ms`;
}

export function formatStatusLabel(status: DeploymentStatus | ProviderStatus | HealthStatus | string) {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
