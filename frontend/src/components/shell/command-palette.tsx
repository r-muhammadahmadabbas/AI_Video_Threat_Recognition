"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Bell, LogOut, Rows3, Search, TimerReset, User } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { useShell } from "@/components/shell/shell-context";
import { NAV_ITEMS } from "@/lib/nav";
import { ruleLabel, severityInfo, type IconComponent } from "@/lib/labels";
import { timeAgo } from "@/lib/time";
import { useDensity } from "@/lib/density";
import { usePerfTier } from "@/lib/perf";
import { cn } from "@/lib/utils";

interface PaletteResult {
  id: string;
  group: "Actions" | "Navigate" | "Incidents";
  label: string;
  hint?: string;
  icon: IconComponent;
  run: () => void;
}

export function CommandPalette() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { incidents, paletteOpen, setPaletteOpen, toggleFeed } = useShell();
  const { mode, setMode } = useDensity();
  const { tier, setTier } = usePerfTier();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const close = () => setPaletteOpen(false);

  const results: PaletteResult[] = [];

  const actions: PaletteResult[] = [
    {
      id: "action-feed",
      group: "Actions",
      label: "Toggle incident feed",
      hint: "F",
      icon: Bell,
      run: () => {
        close();
        toggleFeed();
      },
    },
    {
      id: "action-density",
      group: "Actions",
      label:
        mode === "compact"
          ? "Switch to comfortable density"
          : "Switch to compact density",
      icon: Rows3,
      run: () => {
        close();
        setMode(mode === "compact" ? "comfortable" : "compact");
      },
    },
    {
      id: "action-perf",
      group: "Actions",
      label:
        tier === "full"
          ? "Switch to lite rendering"
          : "Switch to full rendering",
      icon: TimerReset,
      run: () => {
        close();
        setTier(tier === "full" ? "lite" : "full");
      },
    },
    {
      id: "action-logout",
      group: "Actions",
      label: "Sign out",
      icon: LogOut,
      run: () => {
        close();
        logout();
        router.replace("/login");
      },
    },
  ];

  const navResults: PaletteResult[] = NAV_ITEMS.filter(
    (item) => !item.adminOnly || user?.role === "admin",
  ).map((item) => ({
    id: `nav-${item.href}`,
    group: "Navigate",
    label: item.label,
    hint: `G ${item.hotkey.toUpperCase()}`,
    icon: item.icon,
    run: () => {
      close();
      router.push(item.href);
    },
  }));

  const incidentResults: PaletteResult[] = incidents
    .slice(0, 6)
    .map((incident) => ({
      id: `incident-${incident.id}`,
      group: "Incidents",
      label: `#${incident.id} · ${ruleLabel(incident.event_type)}`,
      hint: timeAgo(incident.first_seen_at),
      icon: severityInfo(incident.severity).icon,
      run: () => {
        close();
        router.push(`/incidents/${incident.id}`);
      },
    }));

  const needle = query.trim().toLowerCase();
  const filtered = [...actions, ...navResults, ...incidentResults].filter(
    (result) =>
      needle.length === 0 || result.label.toLowerCase().includes(needle),
  );
  results.push(...filtered);
  const safeActive = Math.min(active, Math.max(0, results.length - 1));

  const handleOpenChange = (open: boolean) => {
    setPaletteOpen(open);
    if (open) {
      setQuery("");
      setActive(0);
    }
  };

  const handleQueryChange = (value: string) => {
    setQuery(value);
    setActive(0);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => Math.min(index + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const result = results[safeActive];
      if (result) result.run();
    }
  };

  return (
    <DialogPrimitive.Root open={paletteOpen} onOpenChange={handleOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="glass fixed left-1/2 top-[12vh] z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 overflow-hidden rounded-xl border border-border-strong shadow-2xl outline-none"
        >
          <DialogPrimitive.Title className="sr-only">
            Command palette
          </DialogPrimitive.Title>
          <div className="flex items-center gap-2 border-b border-border px-4">
            <Search
              className="h-4 w-4 shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              autoFocus
              value={query}
              onChange={(event) => handleQueryChange(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search commands, pages, incidents…"
              aria-label="Search commands"
              className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            <kbd className="shrink-0 rounded border border-border-strong bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              Esc
            </kbd>
          </div>
          <div
            role="listbox"
            aria-label="Results"
            className="max-h-80 overflow-y-auto p-2"
          >
            {results.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                No matches.
              </p>
            ) : (
              results.map((result, index) => {
                const Icon = result.icon;
                const showGroup =
                  index === 0 || results[index - 1].group !== result.group;
                return (
                  <div key={result.id}>
                    {showGroup && (
                      <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                        {result.group}
                      </p>
                    )}
                    <button
                      type="button"
                      role="option"
                      aria-selected={index === safeActive}
                      onMouseEnter={() => setActive(index)}
                      onClick={result.run}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors",
                        index === safeActive
                          ? "bg-surface-3 text-foreground"
                          : "text-muted-foreground",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate">
                        {result.label}
                      </span>
                      {result.hint && (
                        <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                          {result.hint}
                        </span>
                      )}
                    </button>
                  </div>
                );
              })
            )}
          </div>
          <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <User className="h-3 w-3" aria-hidden="true" />
              {user?.email}
            </span>
            <span className="ml-auto font-mono">↑↓ navigate · ↵ run</span>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
