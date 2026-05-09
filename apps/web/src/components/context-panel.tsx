import type { NiaContextSnippet } from "@crucible/shared/crucible-contract";
import { BookOpenText, Search } from "lucide-react";

import { formatDateTime } from "@/lib/format";

export function ContextPanel({ snippets }: { snippets: NiaContextSnippet[] }) {
  const lastSync = snippets
    .map((snippet) => snippet.searchedAt)
    .sort()
    .at(-1);

  return (
    <section className="space-y-6">
      <div className="rounded-md border border-forge/40 bg-forge/10 p-4 text-sm text-forge">
        Nia is not connected. The app will continue with cached repo context.
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="crucible-card">
          <div className="flex items-center gap-2 text-sm font-medium">
            <BookOpenText aria-hidden="true" className="h-4 w-4 text-forge" />
            Indexed sources
          </div>
          <p className="mt-3 text-3xl font-semibold">{snippets.length}</p>
          <p className="mt-1 text-sm text-muted-foreground">Last sync {formatDateTime(lastSync)}</p>
        </div>
        <div className="crucible-card md:col-span-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Search aria-hidden="true" className="h-4 w-4 text-accent" />
            Recent Nia searches
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            {snippets.map((snippet) => (
              <span key={snippet.id} className="inline-flex items-center gap-2 text-muted-foreground">
                <span aria-hidden="true" className="h-1 w-1 bg-accent" />
                {snippet.usedFor}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold tracking-tight">Context snippets used in agent decisions</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {snippets.map((snippet) => (
            <article key={snippet.id} className="crucible-card">
              <div className="text-sm font-semibold">{snippet.title}</div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{snippet.excerpt}</p>
              <p className="mt-4 font-mono text-xs text-muted-foreground">{snippet.source}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
