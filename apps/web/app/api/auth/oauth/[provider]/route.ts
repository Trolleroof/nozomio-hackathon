import { NextRequest, NextResponse } from "next/server";

import {
  oauthVerifierCookieName,
  safeAuthRedirect,
  startInsForgeOAuth,
  type OAuthProvider
} from "@/lib/server-auth";

const providers = new Set<OAuthProvider>(["google", "github"]);

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ provider: string }> }
) {
  const { provider } = await params;
  if (!providers.has(provider as OAuthProvider)) {
    return NextResponse.redirect(new URL("/login?error=unsupported_oauth_provider", request.url));
  }
  try {
    const nextPath = safeAuthRedirect(request.nextUrl.searchParams.get("next"));
    const oauth = await startInsForgeOAuth(provider as OAuthProvider, request.nextUrl.origin, nextPath);
    const response = NextResponse.redirect(oauth.url);
    response.cookies.set(oauthVerifierCookieName, oauth.codeVerifier, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 10
    });
    return response;
  } catch (error) {
    const message = encodeURIComponent(error instanceof Error ? error.message : "oauth_init_failed");
    return NextResponse.redirect(new URL(`/login?error=${message}`, request.url));
  }
}
