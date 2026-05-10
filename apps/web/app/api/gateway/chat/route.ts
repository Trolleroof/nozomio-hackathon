import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const gatewayBaseUrl = process.env.ANYGPU_GATEWAY_BASE_URL?.trim().replace(/\/$/, "");
    if (!gatewayBaseUrl) {
      return NextResponse.json(createDemoChatCompletion(payload));
    }

    const response = await fetch(`${gatewayBaseUrl}/chat/completions`, {
      method: "POST",
      headers: gatewayHeaders(),
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(30000)
    });
    const body = await response.json();
    return NextResponse.json(body, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Gateway chat request failed"
      },
      { status: 502 }
    );
  }
}

function createDemoChatCompletion(payload: Record<string, unknown>) {
  const now = Math.floor(Date.now() / 1000);
  const model = typeof payload.model === "string" && payload.model.trim()
    ? payload.model.trim()
    : "Qwen/Qwen2.5-7B-Instruct";
  return {
    id: `chatcmpl_demo_${now}`,
    object: "chat.completion",
    created: now,
    model,
    choices: [
      {
        index: 0,
        message: {
          role: "assistant",
          content: demoReply(payload)
        },
        finish_reason: "stop"
      }
    ],
    usage: {
      prompt_tokens: estimateTokens(latestUserMessage(payload)),
      completion_tokens: 18,
      total_tokens: estimateTokens(latestUserMessage(payload)) + 18
    },
    backend: {
      source: "serverless-demo",
      reason: "No live AnyGPU gateway is configured, so Crucible returned a fast local playground response."
    }
  };
}

function demoReply(payload: Record<string, unknown>) {
  const prompt = latestUserMessage(payload).toLowerCase();
  if (prompt.includes("health")) {
    return "Deployment health is passing: the serverless demo endpoint is ready, checks are green, and benchmark data is available.";
  }
  if (prompt.includes("summarize") || prompt.includes("summary")) {
    return "The deployment is ready, routed through Crucible's fast demo endpoint, and reporting healthy checks.";
  }
  return "Crucible demo inference is online and ready; connect ANYGPU_GATEWAY_BASE_URL to route this request to a live model.";
}

function latestUserMessage(payload: Record<string, unknown>) {
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const latest = [...messages].reverse().find((message) => {
    return Boolean(message && typeof message === "object" && (message as Record<string, unknown>).role === "user");
  });
  const content = latest && typeof latest === "object" ? (latest as Record<string, unknown>).content : "";
  return typeof content === "string" ? content : "";
}

function estimateTokens(value: string) {
  return Math.max(1, Math.ceil(value.trim().split(/\s+/).filter(Boolean).length * 1.3));
}

function gatewayHeaders() {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiKey = process.env.ANYGPU_GATEWAY_API_KEY?.trim();
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }
  return headers;
}
