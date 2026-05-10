import { ArrowRight, Bot, Gauge, KeyRound, Network, ShieldCheck, TerminalSquare } from "lucide-react";
import Link from "next/link";

import { AnvilArtLarge } from "@/components/anvil-art";
import { BrandMark } from "@/components/brand-mark";

const featureCards = [
  {
    icon: Bot,
    title: "Natural-language deployment planning",
    body: "Describe the model, budget, latency target, and risk tolerance. Crucible turns that into a concrete GPU deployment plan with a provider, accelerator, price estimate, and uncertainty notes."
  },
  {
    icon: Network,
    title: "Provider routing across GPU clouds",
    body: "The control plane compares Modal, SkyPilot, Lambda Cloud, CoreWeave, Prime Intellect, Vast.ai, and Vultr so an agent can pick the cheapest viable path without pretending every provider is live."
  },
  {
    icon: ShieldCheck,
    title: "Human approval before paid launch",
    body: "Personal agents can plan and prepare deployments, but paid GPU provisioning stops at an approval gate. Nothing expensive launches just because a prompt sounded confident."
  },
  {
    icon: TerminalSquare,
    title: "OpenAI-compatible model endpoints",
    body: "Approved deployments expose familiar /v1/models and /v1/chat/completions routes, plus logs, health checks, benchmark data, and stop controls."
  }
];

const flowSteps = [
  "Ask for a deployment in plain English.",
  "Crucible profiles the model and pulls relevant Nia context.",
  "The broker recommends a GPU provider and accelerator.",
  "A human approves the paid launch.",
  "The system provisions, verifies health, and exposes an endpoint."
];

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
              Open dashboard
            </Link>
          </div>
        </div>

        <div className="flex justify-center overflow-hidden lg:justify-end">
          <AnvilArtLarge />
        </div>
      </section>

      <section className="border-y border-border bg-muted/40">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
          <div>
            <p className="crucible-eyebrow">Crucible workflow</p>
            <h2 className="crucible-pixel-wordmark mt-3 max-w-lg text-4xl leading-none sm:text-5xl">
              <span className="crucible-gradient-text">what it</span>
              <span className="text-foreground"> does</span>
            </h2>
          </div>
          <div className="space-y-5 text-base leading-7 text-muted-foreground">
            <p>
              Crucible Compute is a private GPU deployment backend for personal agents.
              It lets an agent safely plan, price, approve, launch, monitor, and stop
              model-serving workloads without handing the agent unchecked cloud-spend
              authority.
            </p>
            <p>
              The workflow centers on deploying a model through
              the cheapest viable GPU route, showing the recommendation, the approval
              checkpoint, provider status, endpoint health, logs, and the context the
              agent used to make the decision.
            </p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-4 sm:grid-cols-2">
          {featureCards.map((feature) => {
            const Icon = feature.icon;

            return (
              <article key={feature.title} className="crucible-card">
                <div className="flex h-10 w-10 items-center justify-center rounded-md border border-border bg-surface-raised text-accent">
                  <Icon aria-hidden="true" className="h-5 w-5" />
                </div>
                <h3 className="mt-5 text-lg font-semibold tracking-tight">{feature.title}</h3>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{feature.body}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="border-y border-border bg-surface/60">
        <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 lg:grid-cols-[1fr_0.9fr]">
          <div>
            <p className="crucible-eyebrow">Deployment path</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight">
              From prompt to endpoint, with the risky step gated.
            </h2>
            <div className="mt-8 space-y-3">
              {flowSteps.map((step, index) => (
                <div key={step} className="grid grid-cols-[2.5rem_1fr] gap-4 border-t border-border pt-4">
                  <span className="font-mono text-sm text-accent">{String(index + 1).padStart(2, "0")}</span>
                  <p className="text-sm leading-6 text-muted-foreground">{step}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="crucible-card-muted">
            <div className="flex items-center gap-2">
              <Gauge aria-hidden="true" className="h-4 w-4 text-forge" />
              <h3 className="text-lg font-semibold tracking-tight">What operators can use</h3>
            </div>
            <dl className="mt-5 divide-y divide-border text-sm">
              <div className="grid gap-2 py-3 sm:grid-cols-[8rem_1fr]">
                <dt className="text-muted-foreground">Dashboard</dt>
                <dd>Active deployments, endpoint console, provider status, and context snippets.</dd>
              </div>
              <div className="grid gap-2 py-3 sm:grid-cols-[8rem_1fr]">
                <dt className="text-muted-foreground">Planner</dt>
                <dd>Prompt, model ID, objective, stop policy, recommended GPU, price estimate, and approval request.</dd>
              </div>
              <div className="grid gap-2 py-3 sm:grid-cols-[8rem_1fr]">
                <dt className="text-muted-foreground">Providers</dt>
                <dd>Honest live, configured, dry-run, failed, and unsupported capability states.</dd>
              </div>
              <div className="grid gap-2 py-3 sm:grid-cols-[8rem_1fr]">
                <dt className="text-muted-foreground">Agent API</dt>
                <dd>Token-based access so outside agents can request plans and inspect deployments.</dd>
              </div>
            </dl>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-5 px-6 py-16 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <p className="crucible-eyebrow">Why it matters</p>
          <h2 className="crucible-pixel-wordmark mt-3 text-4xl leading-none">
            <span className="crucible-gradient-text">agent-safe</span>
            <span className="text-foreground"> gpu ops</span>
          </h2>
        </div>
        <div className="crucible-card lg:col-span-2">
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <KeyRound aria-hidden="true" className="h-5 w-5 text-accent" />
              <h3 className="mt-4 text-base font-semibold tracking-tight">Private by default</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Sessions, approvals, deployment records, logs, health checks, and benchmark
                traces are persisted locally for the prototype instead of depending on a
                hosted account system.
              </p>
            </div>
            <div>
              <ShieldCheck aria-hidden="true" className="h-5 w-5 text-success" />
              <h3 className="mt-4 text-base font-semibold tracking-tight">Built for controlled autonomy</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                The agent can gather context and make a recommendation, but the approval
                boundary keeps cloud credentials, spend, and stop controls visible to the
                operator.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
