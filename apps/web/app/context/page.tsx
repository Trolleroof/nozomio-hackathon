import { AppFrame } from "@/components/app-frame";
import { ContextPanel } from "@/components/context-panel";
import { listContextSnippets } from "@/lib/crucible-data";
import { hasNiaApiKey } from "@/lib/nia-server";

export default async function ContextPage() {
  const contextSnippets = await listContextSnippets();

  return (
    <AppFrame>
      <div className="mb-8">
        <h1 className="text-2xl font-medium tracking-tight">Context</h1>
      </div>
      <ContextPanel niaConnected={hasNiaApiKey()} snippets={contextSnippets} />
    </AppFrame>
  );
}
