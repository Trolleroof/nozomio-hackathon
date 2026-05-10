import { NextResponse } from "next/server";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
    const gatewayBaseUrl = process.env.ANYGPU_GATEWAY_BASE_URL?.trim().replace(/\/$/, "");
    if (!gatewayBaseUrl) {
      return NextResponse.json(
        { error: "No live deployment endpoint is configured." },
        { status: 503 }
      );
    }

    const response = await fetch(`${gatewayBaseUrl}/chat/completions`, {
      method: "POST",
      headers: gatewayHeaders(),
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: AbortSignal.timeout(30000)
    });
    const body = await readJson(response);
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

function gatewayHeaders() {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "User-Agent": "Crucible-Dashboard/0.1"
  };
  const apiKey = process.env.ANYGPU_GATEWAY_API_KEY?.trim();
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }
  return headers;
}

async function readJson(response: Response) {
  const text = await response.text();
  if (!text.trim()) {
    throw new Error(`Gateway chat returned empty body with HTTP ${response.status}.`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Gateway chat returned non-JSON body with HTTP ${response.status}.`);
  }
}
