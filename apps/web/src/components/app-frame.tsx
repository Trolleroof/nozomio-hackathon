import Link from "next/link";

import { SidebarNav } from "@/components/sidebar-nav";
import { demoSession } from "@/lib/session";

export function AppFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="crucible-shell">
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="crucible-sidebar">
          <div className="px-5 py-5">
            <Link href="/" className="block">
              <div className="text-sm font-medium tracking-tight">
                <span className="crucible-gradient-text">Crucible</span>{" "}
                <span className="text-foreground/85">Compute</span>
              </div>
              <div className="mt-1 truncate text-[11px] text-muted-foreground">
                {demoSession.user.email}
              </div>
            </Link>
          </div>
          <SidebarNav />
        </aside>
        <main className="flex-1 px-6 py-10 md:px-10">
          <div className="mx-auto w-full max-w-5xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
