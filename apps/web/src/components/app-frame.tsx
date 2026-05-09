import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { SidebarNav } from "@/components/sidebar-nav";

export function AppFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="crucible-shell">
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="crucible-sidebar">
          <div className="px-5 py-5">
            <Link href="/" className="inline-flex items-center">
              <BrandMark />
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
