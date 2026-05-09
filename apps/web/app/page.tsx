import { ArrowRight, CheckCircle2, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-white text-zinc-950">
      <section className="mx-auto grid min-h-screen max-w-6xl gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-center lg:px-8">
        <div>
          <div className="mb-5 inline-flex rounded-full border border-zinc-200 px-3 py-1 text-sm text-zinc-600">
            Frontend demo against typed fixtures
          </div>
          <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">Crucible Compute</h1>
          <p className="mt-4 max-w-xl text-lg leading-8 text-zinc-600">
            Crucible gives every personal agent its own GPU deployment backend.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/signup"
              className="inline-flex min-h-11 items-center gap-2 rounded-md bg-zinc-950 px-5 py-2 text-sm font-medium text-white hover:bg-zinc-800"
            >
              Start deployment
              <ArrowRight aria-hidden="true" className="h-4 w-4" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex min-h-11 items-center rounded-md border border-zinc-300 px-5 py-2 text-sm font-medium hover:bg-zinc-50"
            >
              View demo dashboard
            </Link>
          </div>
        </div>

        <div className="rounded-md border border-zinc-200 bg-zinc-50 p-5">
          <div className="flex items-center justify-between gap-4 border-b border-zinc-200 pb-4">
            <div>
              <div className="text-sm font-medium">Deploy Qwen 7B cheaply</div>
              <div className="mt-1 text-sm text-zinc-500">Approval gate before paid GPU launch</div>
            </div>
            <StatusBadge status="approval_required">Approval required</StatusBadge>
          </div>
          <div className="grid gap-3 py-5 sm:grid-cols-3">
            <div>
              <div className="text-xs uppercase tracking-wide text-zinc-500">Provider</div>
              <div className="mt-1 text-sm font-medium">Modal</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-zinc-500">GPU</div>
              <div className="mt-1 text-sm font-medium">NVIDIA L4</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-zinc-500">Model</div>
              <div className="mt-1 text-sm font-medium">Qwen 2.5</div>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center gap-2 rounded-md border border-zinc-200 bg-white p-3 text-sm">
              <ShieldCheck aria-hidden="true" className="h-4 w-4" />
              Paid launch needs approval
            </div>
            <div className="flex items-center gap-2 rounded-md border border-zinc-200 bg-white p-3 text-sm">
              <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
              Safe fixture endpoint ready
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
