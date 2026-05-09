import { AgentAccessPanel } from "@/components/agent-access-panel";
import { AppFrame } from "@/components/app-frame";
import { apiTokens } from "@crucible/shared/fixtures";

export default function AgentPage() {
  return (
    <AppFrame>
      <div className="mb-8">
        <p className="crucible-eyebrow">MCP and CLI access for personal agents</p>
        <h1 className="mt-1 text-2xl font-medium tracking-tight">Agent access</h1>
      </div>
      <AgentAccessPanel token={apiTokens[0]} />
    </AppFrame>
  );
}
