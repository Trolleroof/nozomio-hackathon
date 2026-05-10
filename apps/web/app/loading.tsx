import { LoaderCircle } from "lucide-react";

import { AppFrame } from "@/components/app-frame";

export default function Loading() {
  return (
    <AppFrame>
      <section
        aria-label="Loading page"
        className="motion-fade-in space-y-6"
        role="status"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-surface-raised text-accent">
            <LoaderCircle aria-hidden="true" className="h-5 w-5 animate-spin" />
          </span>
          <div>
            <p className="crucible-eyebrow">Switching pages</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
              Loading the next view
            </h1>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-[1.3fr_0.7fr]">
          <div className="crucible-card space-y-4">
            <div className="crucible-skeleton-line h-5 w-2/5 rounded bg-surface-raised" />
            <div className="space-y-2">
              <div className="crucible-skeleton-line h-3 w-full rounded bg-surface-raised" />
              <div className="crucible-skeleton-line h-3 w-5/6 rounded bg-surface-raised" />
              <div className="crucible-skeleton-line h-3 w-3/4 rounded bg-surface-raised" />
            </div>
          </div>
          <div className="crucible-card-muted space-y-3">
            <div className="crucible-skeleton-line h-4 w-1/2 rounded bg-surface-raised" />
            <div className="crucible-skeleton-line h-16 rounded bg-surface-raised" />
          </div>
        </div>
      </section>
    </AppFrame>
  );
}
