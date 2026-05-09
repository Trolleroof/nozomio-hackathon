import { NextResponse } from "next/server";

const gatewayBaseUrl = process.env.ANYGPU_GATEWAY_BASE_URL ?? "http://127.0.0.1:8765/v1";

export async function POST(request: Request) {
  try {
    const payload = await request.json();
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
