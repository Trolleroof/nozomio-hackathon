import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { AnvilArtLarge } from "@/components/anvil-art";

export default function LandingPage() {
  return (
    <main className="crucible-shell">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <Link href="/" className="text-sm font-medium tracking-tight">
            <span className="crucible-gradient-text">Crucible</span>
            <span className="text-foreground/80"> Compute</span>
          </Link>
          <nav className="flex items-center gap-1.5">
            <Link href="/login" className="px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
              Log in
            </Link>
            <Link href="/signup" className="crucible-primary min-h-9 px-3.5">
              Sign up
            </Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto grid max-w-5xl gap-16 px-6 pb-24 pt-20 lg:grid-cols-[1fr_auto] lg:items-center lg:gap-24 lg:pt-28">
        <div className="max-w-xl">
          <p className="crucible-eyebrow">GPU deployment backend</p>
          <h1 className="mt-4 text-5xl font-medium leading-[1.05] tracking-tight sm:text-6xl">
            <span className="crucible-gradient-text">Crucible</span>
            <span className="text-foreground"> Compute</span>
          </h1>
          <p className="mt-5 max-w-md text-base leading-7 text-muted-foreground">
            A private GPU deployment backend for personal agents. Plan it, approve
            it, ship it.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-2">
            <Link href="/signup" className="crucible-primary min-h-10 gap-1.5 px-4">
              Start deployment
              <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
            </Link>
            <Link href="/dashboard" className="crucible-secondary min-h-10 px-4">
              View demo
            </Link>
          </div>

          <dl className="mt-14 grid max-w-md grid-cols-3 gap-x-8 gap-y-1 border-t border-border pt-6 text-sm">
            <div>
              <dt className="crucible-eyebrow">Providers</dt>
              <dd className="mt-1.5 font-medium text-foreground">Modal &middot; Vast &middot; RunPod</dd>
            </div>
            <div>
              <dt className="crucible-eyebrow">Gate</dt>
              <dd className="mt-1.5 font-medium text-foreground">Human approval</dd>
            </div>
            <div>
              <dt className="crucible-eyebrow">Surface</dt>
              <dd className="mt-1.5 font-medium text-foreground">CLI &middot; MCP &middot; UI</dd>
            </div>
          </dl>
        </div>

        <div className="flex justify-center lg:justify-end">
          <AnvilArtLarge />
        </div>
      </section>
    </main>
  );
}
