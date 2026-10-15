"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { useShell } from "@/components/shell/shell-context";
import { NAV_ITEMS } from "@/lib/nav";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";

function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) return false;
  return (
    element.tagName === "INPUT" ||
    element.tagName === "TEXTAREA" ||
    element.tagName === "SELECT" ||
    element.isContentEditable
  );
}

export function Hotkeys() {
  const router = useRouter();
  const { user } = useAuth();
  const { togglePalette, toggleFeed, paletteOpen } = useShell();
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    let pendingG = false;
    let pendingTimer: number | undefined;

    const resetPending = () => {
      pendingG = false;
      if (pendingTimer !== undefined) window.clearTimeout(pendingTimer);
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        togglePalette();
        return;
      }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTypingTarget(event.target) || paletteOpen) return;

      if (event.key === "?") {
        event.preventDefault();
        setHelpOpen(true);
        return;
      }
      if (event.key === "f") {
        event.preventDefault();
        toggleFeed();
        return;
      }
      if (event.key === "g") {
        pendingG = true;
        if (pendingTimer !== undefined) window.clearTimeout(pendingTimer);
        pendingTimer = window.setTimeout(resetPending, 900);
        return;
      }
      if (pendingG) {
        const allowed = NAV_ITEMS.filter(
          (item) => !item.adminOnly || user?.role === "admin",
        );
        const match = allowed.find((item) => item.hotkey === event.key);
        if (match) {
          event.preventDefault();
          router.push(match.href);
        }
        resetPending();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      resetPending();
    };
  }, [router, togglePalette, toggleFeed, paletteOpen, user?.role]);

  const shortcuts = [
    { keys: "Ctrl K", label: "Open command palette" },
    { keys: "G then D", label: "Go to Dashboard" },
    { keys: "G then L", label: "Go to Live stream" },
    { keys: "G then T", label: "Go to Detect" },
    { keys: "G then I", label: "Go to Incidents" },
    { keys: "G then C", label: "Go to Cameras" },
    { keys: "G then Z", label: "Go to Zones" },
    { keys: "G then R", label: "Go to Rules" },
    ...(user?.role === "admin"
      ? [
          { keys: "G then U", label: "Go to Users" },
          { keys: "G then A", label: "Go to Audit log" },
        ]
      : []),
    { keys: "F", label: "Toggle incident feed" },
    { keys: "?", label: "Show this help" },
  ];

  return (
    <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>
            Shortcuts are ignored while typing in a field.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1">
          {shortcuts.map((shortcut) => (
            <div key={shortcut.keys}>
              <div className="flex items-center justify-between py-1.5 text-sm">
                <span className="text-muted-foreground">{shortcut.label}</span>
                <kbd className="rounded border border-border-strong bg-surface-2 px-2 py-0.5 font-mono text-[11px]">
                  {shortcut.keys}
                </kbd>
              </div>
              <Separator className="last:hidden" />
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
