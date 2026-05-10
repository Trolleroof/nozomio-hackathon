"use client";

import { Github } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type OAuthProvider = "google" | "github";

const providerLabels: Record<OAuthProvider, string> = {
  google: "Google",
  github: "GitHub"
};

function providerIcon(provider: OAuthProvider) {
  if (provider === "github") {
    return <Github aria-hidden="true" className="h-4 w-4" />;
  }
  return (
    <span aria-hidden="true" className="grid h-4 w-4 place-items-center font-medium">
      G
    </span>
  );
}

export function AuthOAuthOptions({ nextPath }: { nextPath: "/dashboard" | "/onboarding" }) {
  const [providers, setProviders] = useState<OAuthProvider[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function loadConfig() {
      try {
        const response = await fetch("/api/auth/config", { cache: "no-store" });
        const body = await response.json();
        if (cancelled || !Array.isArray(body?.oAuthProviders)) {
          return;
        }
        setProviders(body.oAuthProviders.filter((provider: string) => provider === "google" || provider === "github"));
      } catch {
        if (!cancelled) {
          setProviders([]);
        }
      }
    }
    void loadConfig();
    return () => {
      cancelled = true;
    };
  }, []);

  const oauthLinks = useMemo(
    () =>
      providers.map((provider) => ({
        href: `/api/auth/oauth/${provider}?next=${encodeURIComponent(nextPath)}`,
        label: `Continue with ${providerLabels[provider]}`,
        provider
      })),
    [nextPath, providers]
  );

  if (oauthLinks.length === 0) {
    return null;
  }

  return (
    <div className="motion-fade-in mt-5 space-y-2">
      {oauthLinks.map((item) => (
        <Link
          className="crucible-secondary min-h-10 w-full gap-2"
          href={item.href}
          key={item.provider}
        >
          {providerIcon(item.provider)}
          {item.label}
        </Link>
      ))}
    </div>
  );
}
