"use client";

import { ShellProvider } from "@/components/shell/shell-context";
import { AppRail } from "@/components/shell/app-rail";
import { Topbar } from "@/components/shell/topbar";
import { IncidentFeed } from "@/components/shell/incident-feed";
import { MobileTabBar } from "@/components/shell/mobile-tab-bar";
import { CommandPalette } from "@/components/shell/command-palette";
import { Hotkeys } from "@/components/shell/hotkeys";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ShellProvider>
      <div className="flex min-h-screen">
        <AppRail />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className="flex-1 p-4 pb-24 md:p-6 md:pb-8">{children}</main>
        </div>
        <IncidentFeed />
        <MobileTabBar />
        <CommandPalette />
        <Hotkeys />
      </div>
    </ShellProvider>
  );
}
