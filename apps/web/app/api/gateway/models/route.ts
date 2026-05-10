import { NextResponse } from "next/server";

export async function GET() {
  const gatewayBaseUrl = process.env.ANYGPU_GATEWAY_BASE_URL?.trim().replace(/\/$/, "");
  if (!gatewayBaseUrl) {
    return NextResponse.json({
      baseUrl: "",
      ok: false,
      status: 0,
      models: [],
      error: "No live AnyGPU gateway is configured."
    });
  }

  try {
    const response = await fetch(`${gatewayBaseUrl}/models`, {
      headers: gatewayHeaders(),
      cache: "no-store",
      signal: AbortSignal.timeout(3000)
    });
    const body = await readJson(response);
    return NextResponse.json(
      {
        baseUrl: gatewayBaseUrl,
        ok: response.ok,
        status: response.status,
        models: Array.isArray(body?.data) ? body.data : [],
        raw: body
      },
      { status: response.ok ? 200 : 502 }
    );
  } catch (error) {
    return NextResponse.json(
      {
        baseUrl: gatewayBaseUrl,
        ok: false,
        status: 0,
        models: [],
        error: error instanceof Error ? error.message : "Gateway request failed"
      },
      { status: 502 }
    );
  }
}

function gatewayHeaders() {
  const apiKey = process.env.ANYGPU_GATEWAY_API_KEY?.trim();
  return {
    "User-Agent": "Crucible-Dashboard/0.1",
    ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {})
  };
}

async function readJson(response: Response) {
  const text = await response.text();
  if (!text.trim()) {
    throw new Error(`Gateway /models returned empty body with HTTP ${response.status}.`);
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`Gateway /models returned non-JSON body with HTTP ${response.status}.`);
  }
}
