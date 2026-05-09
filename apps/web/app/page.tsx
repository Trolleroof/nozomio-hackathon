import { ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";

export default function LandingPage() {
  return (
    <main className="crucible-shell">
      <section className="mx-auto grid min-h-screen max-w-6xl gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-center lg:px-8">
        <div>
          <div className="mb-5 inline-flex rounded-full border border-forge/40 bg-forge/10 px-3 py-1 text-sm text-forge">
            Frontend demo against typed fixtures
          </div>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">Crucible Compute</h1>
          <p className="mt-4 max-w-xl text-lg leading-8 text-muted-foreground">
            Crucible gives every personal agent its own GPU deployment backend.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/signup"
              className="crucible-primary min-h-11 gap-2 px-5"
            >
              Start deployment
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
            <Link
              href="/dashboard"
              className="crucible-secondary min-h-11 px-5"
            >
              View demo dashboard
            </Link>
          </div>
        </div>

        <div className="crucible-card-muted">
          <div className="flex items-center justify-between gap-4 border-b border-border pb-4">
            <div>
              <div className="text-sm font-medium">Deploy Qwen 7B cheaply</div>
              <div className="mt-1 text-sm text-muted-foreground">Approval gate before paid GPU launch</div>
            </div>
            <StatusBadge status="approval_required">Approval required</StatusBadge>
          </div>
          <div className="grid gap-3 py-5 sm:grid-cols-3">
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Provider</div>
              <div className="mt-1 text-sm font-medium">Modal</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">GPU</div>
              <div className="mt-1 text-sm font-medium">NVIDIA L4</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Model</div>
              <div className="mt-1 text-sm font-medium">Qwen 2.5</div>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center gap-2 rounded-md border border-border bg-surface p-3 text-sm">
              <ShieldCheck aria-hidden="true" className="h-4 w-4 text-forge" />
              Paid launch needs approval
            </div>
            <div className="flex items-center gap-2 rounded-md border border-border bg-surface p-3 text-sm">
              <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-success" />
              Safe fixture endpoint ready
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
