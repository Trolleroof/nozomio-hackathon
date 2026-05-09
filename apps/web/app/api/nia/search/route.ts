import { NextResponse } from "next/server";

import { searchNia } from "@/lib/nia-server";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const query = typeof body?.query === "string" ? body.query.trim() : "";
    if (!query) {
      return NextResponse.json({ error: "Query is required." }, { status: 400 });
    }
    return NextResponse.json(await searchNia(query));
  } catch {
    return NextResponse.json({ error: "Nia search request failed." }, { status: 400 });
  }
}
