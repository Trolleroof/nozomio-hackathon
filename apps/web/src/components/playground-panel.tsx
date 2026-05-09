"use client";

import type { Deployment } from "@crucible/shared/crucible-contract";
import type { FormEvent } from "react";
import { useState } from "react";

export function PlaygroundPanel({ deployment }: { deployment: Deployment }) {
  const isReady = deployment.status === "ready";
  const [prompt, setPrompt] = useState("Summarize the deployment health in one sentence.");
  const [status, setStatus] = useState<"idle" | "sending">("idle");
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim()) {
      return;
    }
    setStatus("sending");
    setReply(null);
    setError(null);
    try {
      const response = await fetch("/api/gateway/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: deployment.name,
          messages: [{ role: "user", content: prompt.trim() }],
          temperature: 0.2
        })
      });
      const body = await response.json();
      if (!response.ok) {
        const message = typeof body?.error === "string" ? body.error : body?.error?.message;
        throw new Error(message || "Inference request failed.");
      }
      const content = body?.choices?.[0]?.message?.content ?? body?.choices?.[0]?.text;
      setReply(typeof content === "string" ? content : JSON.stringify(body));
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : "Inference request failed.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <section className="crucible-card">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-tight">Playground</h2>
        <span className="text-xs text-muted-foreground">{deployment.modelId}</span>
      </div>
      {isReady ? (
        <form className="space-y-3" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium" htmlFor="playground-prompt">
            Test prompt
          </label>
          <textarea
            id="playground-prompt"
            className="crucible-textarea min-h-28 w-full"
            onChange={(event) => setPrompt(event.target.value)}
            value={prompt}
          />
          <button
            className="crucible-primary min-h-10"
            disabled={status === "sending"}
            type="submit"
          >
            {status === "sending" ? "Sending" : "Send test request"}
          </button>
          {reply ? (
            <div className="rounded-md border border-border bg-muted p-3 text-sm leading-6 text-foreground">
              {reply}
            </div>
          ) : null}
          {error ? <p className="text-sm text-ember">{error}</p> : null}
        </form>
      ) : (
        <div className="rounded-md border border-dashed border-border bg-muted p-4 text-sm text-muted-foreground">
          Playground unlocks after health checks pass.
        </div>
      )}
    </section>
  );
}
