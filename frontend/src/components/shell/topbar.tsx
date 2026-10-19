"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Bell, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusPill } from "@/components/shell/status-pill";
import { useShell } from "@/components/shell/shell-context";
import { pageTitle } from "@/lib/nav";
import { formatUtcClock } from "@/lib/time";

export function Topbar() {
  const pathname = usePathname();
  const { newCount, toggleFeed, togglePalette } = useShell();
  const [clock, setClock] = useState<string | null>(null);

  useEffect(() => {
    const update = () => setClock(formatUtcClock(new Date()));
    const initial = window.setTimeout(update, 0);
    const timer = window.setInterval(update, 1000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/90 px-4 backdrop-blur md:px-6">
      <p className="truncate text-sm font-semibold tracking-tight">
        {pageTitle(pathname)}
      </p>
      <div className="ml-auto flex items-center gap-2">
        <StatusPill />
        <span className="hidden select-none font-mono text-xs tabular-nums text-muted-foreground lg:block">
          {clock ?? "—:—:— UTC"}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={togglePalette}
          className="gap-2 text-muted-foreground"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden rounded border border-border-strong bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] md:inline">
            Ctrl K
          </kbd>
        </Button>
        <Button
          variant="outline"
          size="icon"
          onClick={toggleFeed}
          aria-label={`Toggle incident feed (${newCount} new)`}
          className="relative"
        >
          <Bell className="h-4 w-4" aria-hidden="true" />
          {newCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sev-critical-solid px-1 text-[10px] font-bold tabular-nums text-white">
              {newCount > 99 ? "99" : newCount}
            </span>
          )}
        </Button>
      </div>
    </header>
  );
}
