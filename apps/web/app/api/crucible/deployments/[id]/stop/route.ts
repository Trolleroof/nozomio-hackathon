import { NextResponse } from "next/server";

import { stopStoredDeployment } from "@/lib/crucible-deployments";

export async function POST(
  _request: Request,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const params = await context.params;
    const deployment = stopStoredDeployment(params.id);
    return NextResponse.json({ deployment });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Stop deployment failed." },
      { status: 404 }
    );
  }
}
