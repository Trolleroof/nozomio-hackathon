"use client";

import type { DeploymentStatus } from "@crucible/shared/crucible-contract";
import { LoaderCircle, TerminalSquare } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

export function DeploymentControls({
  deploymentId,
  initialStatus
}: {
  deploymentId: string;
  initialStatus: DeploymentStatus;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<DeploymentStatus>(initialStatus);
  const [isStopping, setIsStopping] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isStopped = status === "stopped" || status === "stopping";

  async function handleStop() {
    setIsStopping(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(`/api/crucible/deployments/${deploymentId}/stop`, {
        method: "POST"
      });
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.error || "Stop deployment failed.");
      }
      setStatus(body.deployment?.status === "stopped" ? "stopped" : "stopping");
      setMessage("Deployment stopped.");
      router.refresh();
    } catch (stopError) {
      setError(stopError instanceof Error ? stopError.message : "Stop deployment failed.");
    } finally {
      setIsStopping(false);
    }
  }

  return (
    <div className="space-y-3">
      <button
        className="crucible-danger min-h-10 gap-2"
        type="button"
        onClick={handleStop}
        disabled={isStopping || isStopped}
      >
        {isStopping ? (
          <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
        ) : (
          <TerminalSquare aria-hidden="true" className="h-4 w-4" />
        )}
        {isStopping ? "Stopping" : isStopped ? "Stopped" : "Stop deployment"}
      </button>
      {isStopping ? (
        <div
          aria-label="Stop request in progress"
          className="motion-fade-in text-sm text-muted-foreground"
          role="status"
        >
          Stopping deployment
        </div>
      ) : null}
      {message ? <p className="text-sm text-success">{message}</p> : null}
      {error ? <p className="text-sm text-ember">{error}</p> : null}
    </div>
  );
}
