import type { Deployment } from "@crucible/shared/crucible-contract";

export function PlaygroundPanel({ deployment }: { deployment: Deployment }) {
  const isReady = deployment.status === "ready";

  return (
    <section className="rounded-md border border-zinc-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-tight">Playground</h2>
        <span className="text-xs text-zinc-500">{deployment.modelId}</span>
      </div>
      {isReady ? (
        <form className="space-y-3">
          <label className="block text-sm font-medium" htmlFor="playground-prompt">
            Test prompt
          </label>
          <textarea
            id="playground-prompt"
            className="min-h-28 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-950"
            defaultValue="Summarize the deployment health in one sentence."
          />
          <button
            className="inline-flex min-h-10 items-center rounded-md bg-zinc-950 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800"
            type="button"
          >
            Send test request
          </button>
        </form>
      ) : (
        <div className="rounded-md border border-dashed border-zinc-300 bg-zinc-50 p-4 text-sm text-zinc-600">
          Playground unlocks after health checks pass.
        </div>
      )}
    </section>
  );
}
