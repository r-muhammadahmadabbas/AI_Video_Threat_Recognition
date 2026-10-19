"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScanSearch } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { AccountMenu } from "@/components/shell/account-menu";
import { NAV_ITEMS, isNavActive } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function AppRail() {
  const pathname = usePathname();
  const { user } = useAuth();

  const items = NAV_ITEMS.filter(
    (item) => !item.adminOnly || user?.role === "admin",
  );

  return (
    <aside className="sticky top-0 hidden h-screen w-16 shrink-0 flex-col items-center border-r border-border bg-surface-1 py-4 md:flex">
      <Link
        href="/"
        aria-label="Threat Recognition — dashboard"
        className="mb-6 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/15 text-primary transition-colors hover:bg-primary/25"
      >
        <ScanSearch className="h-5 w-5" aria-hidden="true" />
      </Link>

      <nav
        className="flex flex-1 flex-col items-center gap-1"
        aria-label="Primary"
      >
        {items.map((item) => {
          const active = isNavActive(item.href, pathname);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-label={item.label}
              aria-current={active ? "page" : undefined}
              title={item.label}
              className={cn(
                "relative flex h-10 w-10 items-center justify-center rounded-lg transition-colors",
                active
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:bg-surface-3 hover:text-foreground",
              )}
            >
              <item.icon className="h-5 w-5" aria-hidden="true" />
              {active && (
                <span
                  className="absolute -left-3 h-5 w-1 rounded-full bg-primary"
                  aria-hidden="true"
                />
              )}
            </Link>
          );
        })}
      </nav>

      <AccountMenu trigger="avatar" className="mt-2" />
    </aside>
  );
}
