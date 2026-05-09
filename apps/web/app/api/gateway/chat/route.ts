import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import { sessionCookieName } from "@/lib/server-auth";

const gatewayBaseUrl = process.env.ANYGPU_GATEWAY_BASE_URL ?? "http://127.0.0.1:8765/v1";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const insforgeBaseUrl = process.env.INSFORGE_API_BASE_URL?.replace(/\/$/, "");
    if (insforgeBaseUrl && !process.env.ANYGPU_GATEWAY_BASE_URL) {
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
