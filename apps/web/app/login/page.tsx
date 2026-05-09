import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10 text-foreground">
      <section className="crucible-card w-full max-w-md p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Log in</h1>
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
            Log in
          </button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          Need an account? <Link className="font-medium text-forge hover:text-accent-hover" href="/signup">Create account</Link>
        </p>
      </section>
    </main>
  );
}
