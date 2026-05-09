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
      <div className="rounded-md border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-700">
        Nia is not connected. The app will continue with cached repo context.
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-md border border-zinc-200 bg-white p-5">
          <div className="flex items-center gap-2 text-sm font-medium">
            <BookOpenText aria-hidden="true" className="h-4 w-4" />
            Indexed sources
          </div>
          <p className="mt-3 text-3xl font-semibold">{snippets.length}</p>
          <p className="mt-1 text-sm text-zinc-500">Last sync {formatDateTime(lastSync)}</p>
        </div>
        <div className="rounded-md border border-zinc-200 bg-white p-5 md:col-span-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Search aria-hidden="true" className="h-4 w-4" />
            Recent Nia searches
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-sm">
            {snippets.map((snippet) => (
              <span key={snippet.id} className="rounded-full border border-zinc-200 px-3 py-1">
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
            <article key={snippet.id} className="rounded-md border border-zinc-200 bg-white p-5">
              <div className="text-sm font-semibold">{snippet.title}</div>
              <p className="mt-2 text-sm leading-6 text-zinc-600">{snippet.excerpt}</p>
              <p className="mt-4 text-xs text-zinc-500">{snippet.source}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
