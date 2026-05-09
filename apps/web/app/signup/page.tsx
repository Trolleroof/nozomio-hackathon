import Link from "next/link";

import { AnvilArtMark } from "@/components/anvil-art";

export default function SignupPage() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="crucible-gradient-bar" />
      <div className="flex min-h-[calc(100vh-1px)] items-center justify-center px-4 py-10">
        <div className="crucible-glow w-full max-w-md">
          <section className="crucible-card-feature p-6">
            <div className="flex items-center gap-3">
              <AnvilArtMark />
              <div className="text-sm font-semibold tracking-tight">
                <span className="crucible-gradient-text">Crucible</span>{" "}
                <span className="text-foreground">Compute</span>
              </div>
            </div>
            <h1 className="mt-5 text-2xl font-semibold tracking-tight">Create account</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Forge your first deployment.
            </p>
            <form className="mt-6 space-y-4">
              <div>
                <label className="block text-sm font-medium" htmlFor="email">
                  Email
                </label>
                <input id="email" className="crucible-input mt-2 min-h-11 w-full" type="email" />
              </div>
              <div>
                <label className="block text-sm font-medium" htmlFor="password">
                  Password
                </label>
                <input id="password" className="crucible-input mt-2 min-h-11 w-full" type="password" />
              </div>
              <button className="crucible-primary min-h-11 w-full" type="submit">
                Create account
              </button>
            </form>
            <p className="mt-4 text-sm text-muted-foreground">
              Already have access? <Link className="crucible-link" href="/login">Log in</Link>
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
