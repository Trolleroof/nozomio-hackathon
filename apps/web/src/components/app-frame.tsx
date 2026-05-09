"use client";

import {
  BookOpenText,
  Cable,
  LayoutDashboard,
  Rocket,
  ServerCog
} from "lucide-react";
import Link from "next/link";

import { AnvilArtMark } from "@/components/anvil-art";
import { SidebarNav } from "@/components/sidebar-nav";
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
      <div className="crucible-gradient-bar" />
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="crucible-sidebar">
          <div className="flex items-center justify-between gap-4 px-5 py-5 md:block">
            <Link href="/" className="flex items-center gap-3">
              <AnvilArtMark className="hidden md:block" />
              <div>
                <div className="text-sm font-semibold tracking-tight">
                  <span className="crucible-gradient-text">Crucible</span>{" "}
                  <span className="text-foreground">Compute</span>
                </div>
                <div className="mt-0.5 text-[11px] text-muted-foreground">{demoSession.user.email}</div>
              </div>
            </Link>
          </div>
          <SidebarNav items={navItems} />
        </aside>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
