import { ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { AnvilArtLarge } from "@/components/anvil-art";
import { StatusBadge } from "@/components/status-badge";

export default function LandingPage() {
  return (
    <main className="crucible-shell">
      <div className="crucible-gradient-bar" />
      <section className="mx-auto grid min-h-[calc(100vh-1px)] max-w-6xl gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:px-8">
        <div>
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-gradient-to-r from-ember to-forge" />
            GPU deployment backend
          </div>
          <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl">
            <span className="crucible-gradient-text">Crucible</span>
            <span className="text-foreground"> Compute</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-muted-foreground">
            Crucible gives every personal agent its own GPU deployment backend.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/signup" className="crucible-primary min-h-11 gap-2 px-5">
              Start deployment
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
            <Link href="/dashboard" className="crucible-secondary min-h-11 px-5">
              View demo dashboard
            </Link>
          </div>

          <dl className="mt-10 grid max-w-lg grid-cols-3 gap-4 text-sm">
            <div>
              <dt className="crucible-eyebrow">Providers</dt>
              <dd className="mt-1 font-medium text-foreground">Modal, SkyPilot, Vast.ai</dd>
            </div>
            <div>
              <dt className="crucible-eyebrow">Gate</dt>
              <dd className="mt-1 font-medium text-foreground">Human approval</dd>
            </div>
            <div>
              <dt className="crucible-eyebrow">Surface</dt>
              <dd className="mt-1 font-medium text-foreground">CLI &middot; MCP &middot; UI</dd>
            </div>
          </dl>
        </div>

        <div className="crucible-glow flex flex-col gap-6">
          <div className="flex justify-center lg:justify-end">
            <AnvilArtLarge />
          </div>

          <div className="crucible-card-feature">
            <div className="flex items-center justify-between gap-4 border-b border-border/60 pb-4">
              <div>
                <div className="text-sm font-semibold tracking-tight">Deploy Qwen 7B cheaply</div>
                <div className="mt-1 text-sm text-muted-foreground">Approval gate before paid GPU launch</div>
              </div>
              <StatusBadge status="approval_required">Approval required</StatusBadge>
            </div>
            <div className="grid gap-3 py-5 sm:grid-cols-3">
              <div>
                <div className="crucible-eyebrow">Provider</div>
                <div className="mt-1 text-sm font-medium">Modal</div>
              </div>
              <div>
                <div className="crucible-eyebrow">GPU</div>
                <div className="mt-1 text-sm font-medium">NVIDIA L4</div>
              </div>
              <div>
                <div className="crucible-eyebrow">Model</div>
                <div className="mt-1 text-sm font-medium">Qwen 2.5</div>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex items-center gap-2 rounded-md border border-border bg-surface-raised p-3 text-sm">
                <ShieldCheck aria-hidden="true" className="h-4 w-4 text-forge" />
                Paid launch needs approval
              </div>
              <div className="flex items-center gap-2 rounded-md border border-border bg-surface-raised p-3 text-sm">
                <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-success" />
                Safe fixture endpoint ready
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
