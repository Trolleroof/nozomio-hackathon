import type { DeploymentLog } from "@crucible/shared/crucible-contract";

import { StatusBadge } from "@/components/status-badge";
import { formatDateTime } from "@/lib/format";

const secretPattern = /(sk-[A-Za-z0-9_-]+|hf_[A-Za-z0-9_]+|VAST_AI_API_KEY(?:=[^\s]+)?)/g;

function redact(message: string) {
  return message.replace(secretPattern, "[redacted]");
}

export function LogPanel({ logs }: { logs: DeploymentLog[] }) {
  return (
    <div className="overflow-hidden rounded-md border border-zinc-200 bg-zinc-950 text-zinc-100">
      <div className="border-b border-zinc-800 px-4 py-3 text-sm font-medium">Logs</div>
      <div className="divide-y divide-zinc-800">
        {logs.map((log) => (
          <div key={log.id} className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[150px_80px_1fr]">
            <time className="text-zinc-400">{formatDateTime(log.timestamp)}</time>
            <span>
              <StatusBadge status={log.level}>{log.level}</StatusBadge>
            </span>
            <p className="m-0 text-zinc-200">{redact(log.message)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
