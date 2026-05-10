import { NextRequest, NextResponse } from "next/server";

import {
  finishInsForgeOAuth,
  insforgeRefreshCookieName,
  oauthVerifierCookieName,
  safeAuthRedirect,
  sessionCookieName
} from "@/lib/server-auth";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("insforge_code");
  const error = request.nextUrl.searchParams.get("error");
  const nextPath = safeAuthRedirect(request.nextUrl.searchParams.get("next"));
  const verifier = request.cookies.get(oauthVerifierCookieName)?.value;

  if (error || !code || !verifier) {
    return NextResponse.redirect(new URL(`/login?error=${encodeURIComponent(error ?? "oauth_failed")}`, request.url));
  }

  try {
    const result = await finishInsForgeOAuth(code, verifier);
    const response = NextResponse.redirect(new URL(nextPath, request.url));
    response.cookies.set(sessionCookieName, result.session.token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 7
    });
    if (result.session.refreshToken) {
      response.cookies.set(insforgeRefreshCookieName, result.session.refreshToken, {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge: 60 * 60 * 24 * 7
      });
    }
    response.cookies.delete(oauthVerifierCookieName);
    return response;
  } catch (exchangeError) {
    const message = encodeURIComponent(exchangeError instanceof Error ? exchangeError.message : "oauth_exchange_failed");
    return NextResponse.redirect(new URL(`/login?error=${message}`, request.url));
  }
}
