import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { AnvilArtLarge } from "@/components/anvil-art";
import { BrandMark } from "@/components/brand-mark";

export default function LandingPage() {
  return (
    <main className="crucible-shell">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <Link href="/" aria-label="Crucible Compute" className="inline-flex items-center">
            <BrandMark showText={false} />
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

      <section className="mx-auto grid max-w-6xl gap-16 px-6 pb-24 pt-20 lg:grid-cols-[1fr_auto] lg:items-center lg:gap-20 lg:pt-28">
        <div className="max-w-xl">
          <h1 className="crucible-pixel-wordmark text-5xl leading-[0.95] sm:text-6xl">
            <span className="crucible-gradient-text">crucible</span>
            <span className="text-foreground"> compute</span>
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
        </div>

        <div className="flex justify-center overflow-hidden lg:justify-end">
          <AnvilArtLarge />
        </div>
      </section>
    </main>
  );
}
