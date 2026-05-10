import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { sessionCookieName } from "@/lib/server-auth";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const insforgeBaseUrl = process.env.INSFORGE_API_BASE_URL?.replace(/\/$/, "");
    const gatewayBaseUrl = process.env.ANYGPU_GATEWAY_BASE_URL?.trim().replace(/\/$/, "");
    if (insforgeBaseUrl && !gatewayBaseUrl) {
      const sessionToken = (await cookies()).get(sessionCookieName)?.value;
      if (!sessionToken) {
        return NextResponse.json(
          { error: "Sign in before using InsForge-backed inference." },
          { status: 401 }
        );
      }
      const response = await fetch(`${insforgeBaseUrl}/api/ai/chat/completion`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: normalizeInsForgeModel(payload?.model),
          messages: payload?.messages,
          temperature: payload?.temperature,
          maxTokens: payload?.max_tokens
        }),
        cache: "no-store",
        signal: AbortSignal.timeout(30000)
      });
      const body = await response.json();
      return NextResponse.json(normalizeInsForgeChatResponse(body), { status: response.status });
    }

    if (!gatewayBaseUrl) {
      return NextResponse.json(createDemoChatResponse(payload));
    }

    const response = await fetch(`${gatewayBaseUrl}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
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

function createDemoChatResponse(payload: unknown) {
  const record = payload && typeof payload === "object" && !Array.isArray(payload)
    ? payload as Record<string, unknown>
    : {};
  const model = typeof record.model === "string" && record.model.trim()
    ? record.model.trim()
    : "Qwen/Qwen2.5-7B-Instruct";
  const prompt = lastUserMessage(record.messages);
  const content = [
    `${model} is ready on the built-in Crucible demo gateway.`,
    prompt ? `I received: "${prompt}"` : "Send prompts here to validate the OpenAI-compatible chat path.",
    "Configure ANYGPU_GATEWAY_BASE_URL or INSFORGE_API_BASE_URL when you want this route to call a live runtime."
  ].join(" ");

  return {
    id: `chatcmpl_demo_${Date.now()}`,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [
      {
        index: 0,
        message: {
          role: "assistant",
          content
        },
        finish_reason: "stop"
      }
    ],
    anygpu: {
      provider: "Crucible demo",
      runtime: "built-in",
      simulated: true
    }
  };
}

function lastUserMessage(messages: unknown) {
  if (!Array.isArray(messages)) {
    return "";
  }
  const userMessages = messages.filter((message): message is Record<string, unknown> => (
    Boolean(message) &&
    typeof message === "object" &&
    !Array.isArray(message) &&
    (message as Record<string, unknown>).role === "user"
  ));
  const last = userMessages.at(-1);
  return typeof last?.content === "string" ? last.content.trim() : "";
}

function normalizeInsForgeModel(model: unknown) {
  const value = typeof model === "string" && model.trim() ? model.trim() : "";
  if (value.includes("/")) {
    return value.toLowerCase();
  }
  return process.env.INSFORGE_AI_MODEL || "openai/gpt-4o-mini";
}

function normalizeInsForgeChatResponse(body: unknown) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return body;
  }
  const record = body as Record<string, unknown>;
  if (typeof record.text !== "string") {
    return body;
  }
  return {
    ...record,
    choices: [
      {
        message: {
          role: "assistant",
          content: record.text
        }
      }
    ]
  };
}
