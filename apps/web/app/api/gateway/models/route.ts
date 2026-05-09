import { NextResponse } from "next/server";

const gatewayBaseUrl = process.env.ANYGPU_GATEWAY_BASE_URL ?? "http://127.0.0.1:8765/v1";

export async function GET() {
  try {
    const response = await fetch(`${gatewayBaseUrl}/models`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000)
    });
    const body = await response.json();
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
