"use client";

import type { Deployment } from "@crucible/shared/crucible-contract";
import { LoaderCircle, RefreshCw, SendHorizontal, Server, TerminalSquare } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

type GatewayModel = {
  id: string;
  object?: string;
  owned_by?: string;
  anygpu?: {
    health?: string;
    provider?: string;
    runtime?: string;
    route?: string;
    simulated?: boolean;
    test_fixture?: boolean;
    upstream_url?: string;
  };
};

type GatewayStatus = {
  baseUrl: string;
  ok: boolean;
  status: number;
  models: GatewayModel[];
  error?: string;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

const fallbackBaseUrl = "http://127.0.0.1:8765/v1";
const isTest = process.env.NODE_ENV === "test";

export function EndpointConsole({ deployments = [] }: { deployments?: Deployment[] }) {
  const liveDeployments = useMemo(() => (
    deployments
      .filter((deployment) => deployment.status === "ready")
      .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
  ), [deployments]);
  const newestDeployment = liveDeployments[0];
  const [gateway, setGateway] = useState<GatewayStatus>({
    baseUrl: newestDeployment?.endpointUrl ?? fallbackBaseUrl,
    ok: false,
    status: 0,
    models: []
  });
  const [loadingStatus, setLoadingStatus] = useState(!isTest);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState(newestDeployment?.id ?? "");
  const [model, setModel] = useState(newestDeployment?.modelId ?? "local-chat");
  const [prompt, setPrompt] = useState("Say hello from AnyGPU");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const selectedDeployment = liveDeployments.find((deployment) => deployment.id === selectedDeploymentId) ?? newestDeployment;
  const selectedEndpointBase = selectedDeployment?.endpointUrl ?? gateway.baseUrl;

  async function refreshStatus() {
    if (typeof fetch === "undefined") {
      return;
    }
    setLoadingStatus(true);
    try {
      const response = await fetch("/api/gateway/models", { cache: "no-store" });
      const data = (await response.json()) as GatewayStatus;
      setGateway(data);
      if (data.models[0]?.id) {
        setModel((current) => current || data.models[0].id);
      }
    } catch (error) {
      setGateway((current) => ({
        ...current,
        ok: false,
        error: error instanceof Error ? error.message : "Unable to reach gateway"
      }));
    } finally {
      setLoadingStatus(false);
    }
  }

  useEffect(() => {
    if (isTest) {
      return;
    }
    void refreshStatus();
  }, []);

  const statusText = useMemo(() => {
    if (loadingStatus) {
      return "checking";
    }
    return gateway.ok ? "online" : "offline";
  }, [gateway.ok, loadingStatus]);

  const selectedModel = gateway.models.find((item) => item.id === model);
  const routeMode = selectedModel?.anygpu?.test_fixture
    ? "test fixture"
    : selectedModel?.anygpu?.simulated
      ? "simulated"
      : selectedModel
        ? "real runtime"
        : "unknown";

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed || sending) {
      return;
    }
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
    setMessages(nextMessages);
    setPrompt("");
    setChatError(null);
    setSending(true);
    try {
      const response = await fetch("/api/gateway/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model,
          messages: nextMessages.map((message) => ({
            role: message.role,
            content: message.content
          }))
        })
      });
      const data = await response.json();
      if (!response.ok) {
        const error = data?.error;
        const message = typeof error === "string" ? error : error?.message;
        throw new Error(message ?? `Gateway returned ${response.status}`);
      }
      const content = data?.choices?.[0]?.message?.content ?? "No response content returned.";
      setMessages([...nextMessages, { role: "assistant", content }]);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Chat request failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="crucible-card md:col-span-3">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Server aria-hidden="true" className="h-4 w-4 text-accent" />
              <h2 className="text-lg font-semibold tracking-tight">Endpoint</h2>
            </div>
            <button className="crucible-secondary min-h-9 gap-2 px-3 text-sm" type="button" onClick={refreshStatus}>
              <RefreshCw aria-hidden="true" className={`h-4 w-4 ${loadingStatus ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="crucible-card-compact">
              <div className="text-xs text-muted-foreground">Status</div>
              <div className="mt-1 flex items-center gap-2 text-sm font-medium">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    loadingStatus ? "crucible-status-pulse bg-forge" : gateway.ok ? "bg-emerald-500" : "bg-destructive"
                  }`}
                  aria-hidden="true"
                />
                {statusText}
              </div>
            </div>
            <div className="crucible-card-compact">
              {liveDeployments.length ? (
                <>
                  <label className="text-xs text-muted-foreground" htmlFor="live-deployment">
                    Live deployment
                  </label>
                  <select
                    id="live-deployment"
                    className="crucible-input mt-1 min-h-9 w-full text-sm"
                    value={selectedDeployment?.id ?? ""}
                    onChange={(event) => {
                      const deployment = liveDeployments.find((item) => item.id === event.target.value);
                      setSelectedDeploymentId(event.target.value);
                      setModel(deployment?.modelId ?? model);
                      setMessages([]);
                      setChatError(null);
                    }}
                  >
                    {liveDeployments.map((deployment) => (
                      <option key={deployment.id} value={deployment.id}>
                        {deployment.name}
                      </option>
                    ))}
                  </select>
                </>
              ) : (
                <>
                  <div className="text-xs text-muted-foreground">Model</div>
                  <select
                    className="crucible-input mt-1 min-h-9 w-full text-sm"
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                  >
                    {gateway.models.length ? (
                      gateway.models.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.id}
                        </option>
                      ))
                    ) : (
                      <option value={model}>{model}</option>
                    )}
                  </select>
                </>
              )}
            </div>
            <div className="crucible-card-compact">
              <div className="text-xs text-muted-foreground">Route mode</div>
              <div className="mt-1 text-sm font-medium">{selectedDeployment ? selectedDeployment.provider : routeMode}</div>
            </div>
            <div className="crucible-card-compact">
              <div className="text-xs text-muted-foreground">Runtime</div>
              <div className="mt-1 text-sm font-medium">{selectedModel?.anygpu?.runtime ?? selectedDeployment?.accelerator ?? "unknown"}</div>
            </div>
          </div>

          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="text-muted-foreground">base_url</dt>
              <dd className="crucible-code mt-1 break-all px-3 py-2">{selectedEndpointBase}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Models route</dt>
              <dd className="crucible-code mt-1 break-all px-3 py-2">{`${selectedEndpointBase}/models`}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Chat route</dt>
              <dd className="crucible-code mt-1 break-all px-3 py-2">{`${selectedEndpointBase}/chat/completions`}</dd>
            </div>
            {selectedModel?.anygpu?.upstream_url ? (
              <div>
                <dt className="text-muted-foreground">Upstream runtime</dt>
                <dd className="crucible-code mt-1 break-all px-3 py-2">{selectedModel.anygpu.upstream_url}</dd>
              </div>
            ) : null}
          </dl>

          {gateway.error ? (
            <div className="mt-4 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {gateway.error}
            </div>
          ) : null}
        </div>

        <div className="flex min-h-[420px] flex-col rounded-md border border-border bg-background">
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <TerminalSquare aria-hidden="true" className="h-4 w-4 text-forge" />
              <h3 className="text-sm font-semibold">Chat</h3>
            </div>
            {selectedDeployment ? (
              <Link className="crucible-link shrink-0 text-xs" href={`/deployments/${selectedDeployment.id}`}>
                Open deployment
              </Link>
            ) : (
              <span className="truncate text-xs text-muted-foreground">{model}</span>
            )}
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length ? (
              messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`motion-fade-in max-w-[88%] rounded-md border px-3 py-2 text-sm ${
                    message.role === "user"
                      ? "ml-auto border-accent/35 bg-accent/10"
                      : "border-border bg-surface"
                  }`}
                >
                  <div className="mb-1 text-xs font-medium text-muted-foreground">
                    {message.role === "user" ? "You" : "Endpoint"}
                  </div>
                  <div className="whitespace-pre-wrap leading-6">{message.content}</div>
                </div>
              ))
            ) : (
              <div className="flex h-full items-center justify-center rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                Send a prompt to test the selected OpenAI-compatible model.
              </div>
            )}
            {sending ? (
              <div
                aria-label="Endpoint response pending"
                className="motion-fade-in max-w-[88%] rounded-md border border-border bg-surface px-3 py-2 text-sm"
                role="status"
              >
                <div className="mb-1 text-xs font-medium text-muted-foreground">Endpoint</div>
                <div className="flex items-center gap-2 leading-6 text-muted-foreground">
                  <span>Endpoint is thinking</span>
                  <span className="inline-flex items-center gap-1" aria-hidden="true">
                    <span className="crucible-thinking-dot h-1.5 w-1.5 rounded-full bg-current" />
                    <span className="crucible-thinking-dot h-1.5 w-1.5 rounded-full bg-current" />
                    <span className="crucible-thinking-dot h-1.5 w-1.5 rounded-full bg-current" />
                  </span>
                </div>
              </div>
            ) : null}
          </div>

          <form className="border-t border-border p-3" onSubmit={sendMessage}>
            {chatError ? <div className="mb-2 text-sm text-destructive">{chatError}</div> : null}
            <div className="flex gap-2">
              <textarea
                className="crucible-textarea min-h-11 flex-1 resize-none"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={1}
                placeholder="Message the endpoint"
              />
              <button
                aria-label={sending ? "Sending message" : undefined}
                className="crucible-primary h-11 w-11 shrink-0 p-0"
                type="submit"
                disabled={sending}
              >
                {sending ? (
                  <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <SendHorizontal aria-hidden="true" className="h-4 w-4" />
                )}
                <span className="sr-only">{sending ? "Sending message" : "Send"}</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </section>
  );
}
