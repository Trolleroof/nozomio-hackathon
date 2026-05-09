import { AgentAccessPanel } from "@/components/agent-access-panel";
import { AppFrame } from "@/components/app-frame";
import { apiTokens } from "@crucible/shared/fixtures";

export default function AgentPage() {
  return (
    <AppFrame>
      <div className="mb-8">
        <p className="text-sm text-zinc-500">MCP and CLI access for personal agents</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Agent access</h1>
      </div>
      <AgentAccessPanel token={apiTokens[0]} />
    </AppFrame>
  );
}
