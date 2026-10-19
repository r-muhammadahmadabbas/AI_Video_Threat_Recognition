"use client";

import { ShellProvider } from "@/components/shell/shell-context";
import { AppRail } from "@/components/shell/app-rail";
import { Topbar } from "@/components/shell/topbar";
import { IncidentFeed } from "@/components/shell/incident-feed";
import { MobileTabBar } from "@/components/shell/mobile-tab-bar";
import { CommandPalette } from "@/components/shell/command-palette";
import { Hotkeys } from "@/components/shell/hotkeys";
import { PageTransition } from "@/components/shell/page-transition";
import { RouteFocus } from "@/components/shell/route-focus";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ShellProvider>
      <div className="flex min-h-screen">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:border focus:border-border-strong focus:bg-surface-1 focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>
        <AppRail />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main
            id="main-content"
            tabIndex={-1}
            className="flex-1 p-4 pb-24 outline-none md:p-6 md:pb-8"
          >
            <PageTransition>{children}</PageTransition>
          </main>
        </div>
        <IncidentFeed />
        <MobileTabBar />
        <CommandPalette />
        <Hotkeys />
        <RouteFocus />
      </div>
    </ShellProvider>
  );
}
