"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  TrendingUp,
  Map,
  RefreshCw,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import clsx from "clsx";
import type { Persona } from "@/lib/demo-personas";

const STORAGE_KEY = "localmate_nav_collapsed";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Dashboard",
    items: [
      { href: "/dashboard", label: "Review Queue", icon: <LayoutDashboard className="h-4 w-4" /> },
    ],
  },
  {
    label: "Growth",
    items: [
      { href: "/dashboard/growth", label: "Rankings & Competitors", icon: <TrendingUp className="h-4 w-4" /> },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/dashboard/locations", label: "Locations", icon: <Map className="h-4 w-4" /> },
      { href: "/dashboard/rebook", label: "Rebook", icon: <RefreshCw className="h-4 w-4" /> },
    ],
  },
];

interface SidebarProps {
  persona?: Persona | null;
}

export default function Sidebar({ persona }: SidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(true);

  // Hydrate from localStorage on mount.
  useEffect(() => {
    if (window.localStorage.getItem(STORAGE_KEY) !== "0") return;
    const t = setTimeout(() => setCollapsed(false), 0);
    return () => clearTimeout(t);
  }, []);

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  const isActive = (href: string) =>
    href === "/dashboard"
      ? pathname === href
      : pathname.startsWith(href);

  const businessName = persona?.businessName ?? "LocalMate";
  const planName = persona?.plan ?? "";

  return (
    <aside
      className={clsx(
        "flex shrink-0 flex-col border-r border-sidebar-border bg-sidebar p-3 transition-[width] duration-150",
        collapsed ? "w-16" : "w-56"
      )}
    >
      {/* Logo */}
      <div
        className={clsx(
          "mb-3 flex items-center gap-2 border-b border-sidebar-border pb-3",
          collapsed && "justify-center"
        )}
      >
        <div className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-amber-600 text-xs font-bold text-white">
          LM
        </div>
        {!collapsed && (
          <div>
            <p className="text-sm font-semibold text-sidebar-foreground">
              Local<span className="text-accent">Mate</span>
            </p>
            <p className="text-xs text-muted-foreground">by CrewCircle</p>
          </div>
        )}
      </div>

      {/* Nav groups */}
      <nav className="flex flex-1 flex-col gap-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {group.label}
              </p>
            )}
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={collapsed ? item.label : undefined}
                    className={clsx(
                      "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                      collapsed && "justify-center px-2",
                      active
                        ? "bg-primary text-primary-foreground"
                        : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                    )}
                  >
                    {item.icon}
                    {!collapsed && item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer: Settings + business info + toggle */}
      <div className="mt-auto space-y-1 border-t border-sidebar-border pt-3">
        <Link
          href="/dashboard/settings"
          title={collapsed ? "Settings" : undefined}
          className={clsx(
            "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            collapsed && "justify-center px-2",
            isActive("/dashboard/settings")
              ? "bg-primary text-primary-foreground"
              : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
          )}
        >
          <Settings className="h-4 w-4" />
          {!collapsed && "Settings"}
        </Link>

        {!collapsed && persona && (
          <div className="px-3 py-1">
            <p className="truncate text-xs font-medium text-sidebar-foreground">
              {businessName}
            </p>
            {planName && (
              <span className="inline-block mt-0.5 rounded bg-sidebar-accent px-1.5 py-0.5 text-[10px] font-medium text-accent">
                {planName}
              </span>
            )}
          </div>
        )}

        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand menu" : "Collapse menu"}
          className="flex w-full items-center justify-center rounded-lg p-2 text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground transition-colors"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
