import {
  BookOpenText,
  Cable,
  LayoutDashboard,
  Rocket,
  ServerCog
} from "lucide-react";
import Link from "next/link";

import { demoSession } from "@/lib/session";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/deployments/new", label: "Deploy", icon: Rocket },
  { href: "/providers", label: "Providers", icon: ServerCog },
  { href: "/context", label: "Context", icon: BookOpenText },
  { href: "/agent", label: "Agent access", icon: Cable }
];

export function AppFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="crucible-shell">
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="crucible-sidebar">
          <div className="flex items-center justify-between gap-4 px-5 py-4 md:block">
            <Link href="/" className="text-sm font-semibold tracking-tight text-forge">
              Crucible Compute
            </Link>
            <div className="text-xs text-muted-foreground md:mt-1">{demoSession.user.email}</div>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:block md:space-y-1 md:px-3">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="crucible-sidebar-link"
                >
                  <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                  <span className="whitespace-nowrap">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
