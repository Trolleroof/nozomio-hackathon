import { NextResponse } from "next/server";

import { login, sessionCookieName } from "@/lib/server-auth";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const result = await login(body?.email, body?.password);
    const response = NextResponse.json({ user: result.user });
    response.cookies.set(sessionCookieName, result.session.token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 7
    });
    return response;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Login failed." },
      { status: 401 }
    );
  }
}
