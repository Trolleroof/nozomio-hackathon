import type { Deployment } from "@crucible/shared/crucible-contract";

export function PlaygroundPanel({ deployment }: { deployment: Deployment }) {
  const isReady = deployment.status === "ready";

  return (
    <section className="crucible-card">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-tight">Playground</h2>
        <span className="text-xs text-muted-foreground">{deployment.modelId}</span>
      </div>
      {isReady ? (
        <form className="space-y-3">
          <label className="block text-sm font-medium" htmlFor="playground-prompt">
            Test prompt
          </label>
          <textarea
            id="playground-prompt"
            className="crucible-textarea min-h-28 w-full"
            defaultValue="Summarize the deployment health in one sentence."
          />
          <button
            className="crucible-primary min-h-10"
            type="button"
          >
            Send test request
          </button>
        </form>
      ) : (
        <div className="rounded-md border border-dashed border-border bg-muted p-4 text-sm text-muted-foreground">
          Playground unlocks after health checks pass.
        </div>
      )}
    </section>
  );
}
