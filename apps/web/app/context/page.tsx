import { AppFrame } from "@/components/app-frame";
import { ContextPanel } from "@/components/context-panel";
import { contextSnippets } from "@crucible/shared/fixtures";

export default function ContextPage() {
  return (
    <AppFrame>
      <div className="mb-8">
        <h1 className="text-2xl font-medium tracking-tight">Context</h1>
      </div>
      <ContextPanel snippets={contextSnippets} />
    </AppFrame>
  );
}
