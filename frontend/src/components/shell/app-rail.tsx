"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, ScanSearch } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { NAV_ITEMS, isNavActive } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function AppRail() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const items = NAV_ITEMS.filter(
    (item) => !item.adminOnly || user?.role === "admin",
  );

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    router.replace("/login");
  };

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
              title={`${item.label} (g ${item.hotkey})`}
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

      <button
        type="button"
        onClick={() => setMenuOpen(true)}
        aria-label="Account menu"
        className="mt-2 flex h-9 w-9 items-center justify-center rounded-full bg-surface-3 text-sm font-semibold text-foreground transition-colors hover:ring-2 hover:ring-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {user?.email?.[0]?.toUpperCase() ?? "?"}
      </button>

      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{user?.full_name || user?.email}</DialogTitle>
            <DialogDescription className="capitalize">
              {user?.role} account
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="sm:justify-end">
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={handleLogout}
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Sign out
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
