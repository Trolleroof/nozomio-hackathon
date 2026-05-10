"use client";

import type { NiaContextSnippet } from "@crucible/shared/crucible-contract";
import { BookOpenText, Search } from "lucide-react";
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
        {niaConnected
          ? "Nia is connected. Search live indexed context for deployment decisions."
          : "Nia is not connected. Configure NIA_API_KEY to search indexed context."}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="crucible-card">
          <div className="flex items-center gap-2 text-sm font-medium">
            <BookOpenText aria-hidden="true" className="h-4 w-4 text-forge" />
            Indexed sources
          </div>
          <p className="mt-3 text-3xl font-semibold">{activeSnippets.length}</p>
          <p className="mt-1 text-sm text-muted-foreground">Last sync {formatDateTime(lastSync)}</p>
        </div>
        <div className="crucible-card md:col-span-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Search aria-hidden="true" className="h-4 w-4 text-accent" />
            Recent Nia searches
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            {activeSnippets.length ? (
              activeSnippets.map((snippet) => (
                <span key={snippet.id} className="inline-flex items-center gap-2 text-muted-foreground">
                  <span aria-hidden="true" className="h-1 w-1 bg-accent" />
                  {snippet.usedFor}
                </span>
              ))
            ) : (
              <span className="text-muted-foreground">No live searches yet.</span>
            )}
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
                <div className="text-sm font-semibold">{snippet.title}</div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{snippet.excerpt}</p>
                <p className="mt-4 font-mono text-xs text-muted-foreground">{snippet.source}</p>
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
