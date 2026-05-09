import { AppFrame } from "@/components/app-frame";
import { ContextPanel } from "@/components/context-panel";
import { contextSnippets } from "@crucible/shared/fixtures";

export default function ContextPage() {
  return (
    <AppFrame>
      <div className="mb-8">
        <p className="text-sm text-zinc-500">Cached Nia context visible to judges and agents</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Context</h1>
      </div>
      <ContextPanel snippets={contextSnippets} />
    </AppFrame>
  );
}
