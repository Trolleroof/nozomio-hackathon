"use client";

import { LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useState } from "react";

import { AuthOAuthOptions } from "@/components/auth-oauth-options";
import { BrandMark } from "@/components/brand-mark";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("submitting");
    setError(null);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.error || "Login failed.");
      }
      router.push("/dashboard");
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Login failed.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-10 text-foreground">
      <section className="motion-fade-in w-full max-w-sm">
        <Link href="/" className="inline-flex items-center">
          <BrandMark iconClassName="h-8 w-8" />
        </Link>
        <h1 className="mt-8 text-2xl font-medium tracking-tight">Log in</h1>
        <AuthOAuthOptions nextPath="/dashboard" />
        <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="block text-sm font-medium" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              autoComplete="email"
              className="crucible-input mt-1.5 min-h-10 w-full"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </div>
          <div>
            <label className="block text-sm font-medium" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              autoComplete="current-password"
              className="crucible-input mt-1.5 min-h-10 w-full"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </div>
          {error ? <p className="text-sm text-ember">{error}</p> : null}
          {status === "submitting" ? (
            <div
              aria-label="Login in progress"
              className="motion-fade-in rounded-md border border-border bg-surface-raised p-3 text-sm text-muted-foreground"
              role="status"
            >
              <div className="flex items-center gap-2">
                <span>Checking credentials</span>
                <span className="inline-flex items-center gap-1" aria-hidden="true">
                  <span className="crucible-thinking-dot h-1.5 w-1.5 rounded-full bg-current" />
                  <span className="crucible-thinking-dot h-1.5 w-1.5 rounded-full bg-current" />
                  <span className="crucible-thinking-dot h-1.5 w-1.5 rounded-full bg-current" />
                </span>
              </div>
            </div>
          ) : null}
          <button className="crucible-primary mt-2 min-h-10 w-full gap-2" disabled={status === "submitting"} type="submit">
            {status === "submitting" ? <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" /> : null}
            {status === "submitting" ? "Logging in" : "Log in"}
          </button>
        </form>
        <p className="mt-6 text-sm text-muted-foreground">
          Need an account? <Link className="crucible-link" href="/signup">Create account</Link>
        </p>
      </section>
    </main>
  );
}
