import { NextResponse } from "next/server";

const demoModel = {
  id: "Qwen/Qwen2.5-7B-Instruct",
  object: "model",
  owned_by: "crucible",
  anygpu: {
    health: "healthy",
    provider: "Crucible demo",
    runtime: "built-in",
    route: "demo",
    simulated: true
  }
};

export async function GET() {
  const gatewayBaseUrl = process.env.ANYGPU_GATEWAY_BASE_URL?.trim().replace(/\/$/, "");
  if (!gatewayBaseUrl) {
    return NextResponse.json({
      baseUrl: "/api/gateway",
      ok: true,
      status: 200,
      models: [demoModel],
      raw: {
        object: "list",
        data: [demoModel]
      }
    });
  }

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
