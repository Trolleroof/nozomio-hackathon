import { NextResponse } from "next/server";

import {
  deployPlan,
  deploymentCookieIndexName,
  deploymentCookieName,
  encodeDeploymentCookie
} from "@/lib/crucible-deployments";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const deployment = await deployPlan(body?.plan);
    const response = NextResponse.json({ deployment });
    const existingIds = deploymentIdsFromCookie(request.headers.get("cookie") ?? "");
    const deploymentIds = [
      deployment.id,
      ...existingIds.filter((id) => id !== deployment.id)
    ].slice(0, 8);

    response.cookies.set(deploymentCookieIndexName, deploymentIds.join(","), {
      path: "/",
      sameSite: "lax",
      maxAge: 60 * 60 * 24
    });
    response.cookies.set(deploymentCookieName(deployment.id), encodeDeploymentCookie(deployment), {
      path: "/",
      sameSite: "lax",
      maxAge: 60 * 60 * 24
    });

    return response;
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Deployment failed." },
      { status: 400 }
    );
  }
}

function deploymentIdsFromCookie(cookieHeader: string) {
  return cookieHeader
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${deploymentCookieIndexName}=`))
    ?.slice(deploymentCookieIndexName.length + 1)
    .split(",")
    .map((id) => decodeURIComponent(id).trim())
    .filter(Boolean) ?? [];
}
