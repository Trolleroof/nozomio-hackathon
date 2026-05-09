import Link from "next/link";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 py-10">
      <section className="w-full max-w-md rounded-md border border-zinc-200 bg-white p-6">
        <h1 className="text-2xl font-semibold tracking-tight">Log in</h1>
        <form className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium" htmlFor="email">
              Email
            </label>
            <input id="email" className="mt-2 min-h-11 w-full rounded-md border border-zinc-300 px-3" type="email" />
          </div>
          <div>
            <label className="block text-sm font-medium" htmlFor="password">
              Password
            </label>
            <input id="password" className="mt-2 min-h-11 w-full rounded-md border border-zinc-300 px-3" type="password" />
          </div>
          <button className="min-h-11 w-full rounded-md bg-zinc-950 px-4 text-sm font-medium text-white" type="submit">
            Log in
          </button>
        </form>
        <p className="mt-4 text-sm text-zinc-600">
          Need an account? <Link className="font-medium text-zinc-950" href="/signup">Create account</Link>
        </p>
      </section>
    </main>
  );
}
