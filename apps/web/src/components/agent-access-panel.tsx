import type { ApiToken } from "@crucible/shared/crucible-contract";
import { Cable, KeyRound, TerminalSquare } from "lucide-react";

export function AgentAccessPanel({ token }: { token: ApiToken }) {
  return (
    <section className="space-y-5">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="crucible-card">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Cable aria-hidden="true" className="h-4 w-4 text-accent" />
            MCP server
          </div>
          <code className="mt-3 block rounded-md border border-border bg-code px-3 py-2 font-mono text-sm text-foreground">
            npx crucible-mcp --url https://crucible.example/mcp
          </code>
        </div>
        <div className="crucible-card">
          <div className="flex items-center gap-2 text-sm font-medium">
            <KeyRound aria-hidden="true" className="h-4 w-4 text-forge" />
            API token
          </div>
          <p className="mt-3 text-2xl font-semibold">{token.prefix}</p>
          <p className="mt-1 text-sm text-muted-foreground">{token.name}</p>
        </div>
        <div className="crucible-card">
          <div className="flex items-center gap-2 text-sm font-medium">
            <TerminalSquare aria-hidden="true" className="h-4 w-4 text-accent" />
            CLI
          </div>
          <p className="mt-3 text-sm text-muted-foreground">Plan, approve, deploy, and inspect from agent workflows.</p>
        </div>
      </div>

      <div className="crucible-card">
        <h2 className="text-lg font-semibold tracking-tight">Hermes/OpenClaw config</h2>
        <pre className="crucible-code mt-3 overflow-x-auto"><code>{`{
  "mcpServers": {
    "crucible": {
      "command": "npx",
      "args": ["crucible-mcp"],
      "env": {
        "CRUCIBLE_API_TOKEN": "${token.prefix}_..."
      }
    }
  }
}`}</code></pre>
      </div>

      <div className="crucible-card">
        <h2 className="text-lg font-semibold tracking-tight">Example MCP tool call</h2>
        <div className="mt-3 text-sm font-medium">crucible_plan_deployment</div>
        <pre className="crucible-code mt-2 overflow-x-auto"><code>{`{
  "prompt": "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
  "objective": "cheapest",
  "modelId": "Qwen/Qwen2.5-7B-Instruct"
}`}</code></pre>
      </div>

      <div className="rounded-md border border-forge/50 bg-forge/10 p-5 text-sm text-forge">
        Approval required before launching GPU resources.
      </div>

      <div className="crucible-card">
        <h2 className="text-lg font-semibold tracking-tight">CLI commands</h2>
        <pre className="crucible-code mt-3 overflow-x-auto"><code>{`crucible plan --prompt "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required."
crucible approve --plan-id plan_qwen_7b
crucible deploy --plan-id plan_qwen_7b --approval-token appr_demo
crucible status --deployment-id dep_qwen_modal`}</code></pre>
      </div>
    </section>
  );
}
