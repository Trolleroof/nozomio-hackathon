"use client";

import type { NiaContextSnippet } from "@crucible/shared/crucible-contract";
import { BadgeCheck, BookOpenText, BrainCircuit, Network, Search } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import { formatDateTime } from "@/lib/format";

interface ContextPanelProps {
  niaConnected: boolean;
  snippets: NiaContextSnippet[];
}

export function ContextPanel({ niaConnected, snippets }: ContextPanelProps) {
  const [query, setQuery] = useState("Qwen 7B deployment health check");
  const [activeSnippets, setActiveSnippets] = useState(snippets);
  const [status, setStatus] = useState(niaConnected ? "ready" : "idle");
  const [error, setError] = useState<string | null>(null);
  const lastSync = useMemo(() => activeSnippets
    .map((snippet) => snippet.searchedAt)
    .sort()
    .at(-1), [activeSnippets]);
  const sourceCount = useMemo(() => new Set(activeSnippets.map((snippet) => sourceHost(snippet.source))).size, [activeSnippets]);
  const decisionChecks = useMemo(() => uniqueDecisionChecks(activeSnippets), [activeSnippets]);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }
    setStatus("searching");
    setError(null);
    try {
      const response = await fetch("/api/nia/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: trimmed })
      });
      const body = await response.json();
      if (!response.ok || !Array.isArray(body.snippets)) {
        throw new Error(body.error || "Nia search failed.");
      }
      setActiveSnippets(body.snippets);
      setStatus(body.connected ? "ready" : "cached");
      setError(body.error ?? null);
    } catch (searchError) {
      setStatus("cached");
      setError(searchError instanceof Error ? searchError.message : "Nia search failed.");
    }
  }

  return (
    <section className="space-y-6">
      <div className="rounded-md border border-forge/40 bg-forge/10 p-4 text-sm text-forge">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-medium">
              {niaConnected
                ? "Nia is connected and grounding deployment decisions in live indexed context."
                : "Nia is not connected. Configure NIA_API_KEY to search indexed context."}
            </p>
            <p className="mt-1 text-forge/80">
              Every recommendation cites the source, the decision it changed, and the latest sync time.
            </p>
          </div>
          <span className="inline-flex w-fit items-center gap-2 rounded-md border border-forge/30 bg-background/40 px-3 py-2 font-mono text-xs">
            <BadgeCheck aria-hidden="true" className="h-4 w-4" />
            {activeSnippets.length ? `${activeSnippets.length} evidence hits ready` : "waiting for evidence"}
          </span>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="crucible-card">
          <div className="flex items-center gap-2 text-sm font-medium">
            <BookOpenText aria-hidden="true" className="h-4 w-4 text-forge" />
            Evidence hits
          </div>
          <p className="mt-3 text-3xl font-semibold">{activeSnippets.length}</p>
          <p className="mt-1 text-sm text-muted-foreground">Last sync {formatDateTime(lastSync)}</p>
        </div>
        <div className="crucible-card">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Network aria-hidden="true" className="h-4 w-4 text-accent" />
            Source coverage
          </div>
          <p className="mt-3 text-3xl font-semibold">{sourceCount}</p>
          <p className="mt-1 text-sm text-muted-foreground">Distinct repos, docs, or API surfaces checked</p>
        </div>
        <div className="crucible-card">
          <div className="flex items-center gap-2 text-sm font-medium">
            <BrainCircuit aria-hidden="true" className="h-4 w-4 text-ember" />
            Decisions grounded
          </div>
          <p className="mt-3 text-3xl font-semibold">{decisionChecks.length}</p>
          <p className="mt-1 text-sm text-muted-foreground">Plan choices with cited Nia evidence</p>
        </div>
      </div>

      <div className="crucible-card">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Search aria-hidden="true" className="h-4 w-4 text-accent" />
          Recent Nia decision checks
        </div>
        <div className="mt-3 grid gap-2 text-sm md:grid-cols-2">
          {decisionChecks.length ? (
            decisionChecks.map((check) => (
              <div key={check} className="rounded-md border border-border bg-surface-raised px-3 py-2 text-muted-foreground">
                <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-accent align-middle" aria-hidden="true" />
                {check}
              </div>
            ))
          ) : (
            <span className="text-muted-foreground">No live searches yet.</span>
          )}
        </div>
      </div>

      <div className="crucible-card-muted">
        <div className="flex items-center gap-2 text-sm font-medium">
          <BadgeCheck aria-hidden="true" className="h-4 w-4 text-forge" />
          What Nia proved for this deployment
        </div>
        <div className="mt-3 grid gap-3 text-sm md:grid-cols-3">
          <div>
            <p className="font-medium">Endpoint readiness</p>
            <p className="mt-1 text-muted-foreground">Checks `/health`, `/v1/models`, and chat completion signals before launch.</p>
          </div>
          <div>
            <p className="font-medium">Provider fit</p>
            <p className="mt-1 text-muted-foreground">Compares live adapter support against dry-run or manually configured providers.</p>
          </div>
          <div>
            <p className="font-medium">Approval risk</p>
            <p className="mt-1 text-muted-foreground">Keeps paid GPU launch decisions behind cited context and explicit approval.</p>
          </div>
        </div>
      </div>

      <form className="crucible-card space-y-3" onSubmit={handleSearch}>
        <label className="block text-sm font-medium" htmlFor="nia-search">
          Search Nia context
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id="nia-search"
            className="crucible-input min-h-11 flex-1"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button className="crucible-primary min-h-11 px-5" disabled={status === "searching"} type="submit">
            {status === "searching" ? "Searching" : "Search"}
          </button>
        </div>
        {error ? <p className="text-sm text-ember">{error}</p> : null}
      </form>

      <div>
        <h2 className="text-lg font-semibold tracking-tight">Context snippets used in agent decisions</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {activeSnippets.length ? (
            activeSnippets.map((snippet) => (
              <article key={snippet.id} className="crucible-card">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="text-sm font-semibold">{snippet.title}</div>
                    <p className="mt-1 font-mono text-xs text-muted-foreground">{sourceHost(snippet.source)}</p>
                  </div>
                  <span className="inline-flex w-fit shrink-0 rounded-md border border-forge/30 bg-forge/10 px-2.5 py-1 text-xs font-medium text-forge">
                    cited in plan
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{snippet.excerpt}</p>
                <div className="mt-4 rounded-md border border-border bg-surface-raised p-3 text-sm">
                  <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">Decision impact</p>
                  <p className="mt-1 text-foreground">{decisionLabel(snippet.usedFor)}</p>
                </div>
              </article>
            ))
          ) : (
            <div className="crucible-card md:col-span-2">
              <p className="text-sm leading-6 text-muted-foreground">
                No context snippets yet. Configure NIA_API_KEY or run a search to populate live context.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function sourceHost(source: string) {
  return source.replace(/^nia:\/\//, "").replace(/^https?:\/\//, "").split(/[/?#]/)[0] || "indexed source";
}

function decisionLabel(usedFor: string) {
  return usedFor.replace(/^Nia search:\s*/i, "");
}

function uniqueDecisionChecks(snippets: NiaContextSnippet[]) {
  return Array.from(new Set(snippets.map((snippet) => decisionLabel(snippet.usedFor)))).slice(0, 6);
}
