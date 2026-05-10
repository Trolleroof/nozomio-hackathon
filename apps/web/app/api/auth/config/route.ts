import { NextResponse } from "next/server";

import { getAuthConfig } from "@/lib/server-auth";

export async function GET() {
  return NextResponse.json(await getAuthConfig());
}
