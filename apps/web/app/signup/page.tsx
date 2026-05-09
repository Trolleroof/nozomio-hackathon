import Link from "next/link";

export default function SignupPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-10 text-foreground">
      <section className="w-full max-w-sm">
        <Link href="/" className="block text-sm font-medium tracking-tight">
          <span className="crucible-gradient-text">Crucible</span>
          <span className="text-foreground/85"> Compute</span>
        </Link>
        <h1 className="mt-8 text-2xl font-medium tracking-tight">Create account</h1>
        <form className="mt-8 space-y-4">
          <div>
            <label className="block text-sm font-medium" htmlFor="email">
              Email
            </label>
            <input id="email" className="crucible-input mt-1.5 min-h-10 w-full" type="email" />
          </div>
          <div>
            <label className="block text-sm font-medium" htmlFor="password">
              Password
            </label>
            <input id="password" className="crucible-input mt-1.5 min-h-10 w-full" type="password" />
          </div>
          <button className="crucible-primary mt-2 min-h-10 w-full" type="submit">
            Create account
          </button>
        </form>
        <p className="mt-6 text-sm text-muted-foreground">
          Already have access? <Link className="crucible-link" href="/login">Log in</Link>
        </p>
      </section>
    </main>
  );
}
