import { AgentAccessPanel } from "@/components/agent-access-panel";
import { AppFrame } from "@/components/app-frame";
import { listApiTokens } from "@/lib/crucible-data";

export default function AgentPage() {
  const apiTokens = listApiTokens();

  return (
    <AppFrame>
      <div className="mb-8">
        <h1 className="text-2xl font-medium tracking-tight">Agent access</h1>
      </div>
      <AgentAccessPanel token={apiTokens[0]} />
    </AppFrame>
  );
}
