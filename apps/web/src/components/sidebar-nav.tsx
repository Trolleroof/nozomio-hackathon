"use client";

import {
  BookOpenText,
  Cable,
  LayoutDashboard,
  Rocket,
  ServerCog,
  type LucideIcon
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/deployments/new", label: "Deploy", icon: Rocket },
  { href: "/providers", label: "Providers", icon: ServerCog },
  { href: "/context", label: "Context", icon: BookOpenText },
  { href: "/agent", label: "Agent access", icon: Cable }
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:block md:space-y-0.5 md:px-3">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const active =
          pathname === item.href ||
          (item.href !== "/" && pathname?.startsWith(item.href));
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`crucible-sidebar-link${active ? " crucible-sidebar-link-active" : ""}`}
          >
            <Icon
              aria-hidden="true"
              className={`h-4 w-4 shrink-0 ${active ? "text-foreground" : "text-muted-foreground"}`}
            />
            <span className="whitespace-nowrap">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
