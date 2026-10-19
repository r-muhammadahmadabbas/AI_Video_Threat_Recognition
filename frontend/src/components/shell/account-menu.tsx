"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, Settings } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { useDensity } from "@/lib/density";
import { usePerfTier } from "@/lib/perf";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export function AccountMenu({
  trigger,
  className,
}: {
  trigger: "avatar" | "icon";
  className?: string;
}) {
  const router = useRouter();
  const { user, logout } = useAuth();
  const { mode, setMode } = useDensity();
  const { tier, setTier } = usePerfTier();
  const [open, setOpen] = useState(false);

  const handleLogout = () => {
    setOpen(false);
    logout();
    router.replace("/login");
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={
          trigger === "avatar" ? "Account menu" : "Display and account settings"
        }
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          trigger === "avatar"
            ? "rounded-full bg-surface-3 text-sm font-semibold text-foreground hover:ring-2 hover:ring-ring"
            : "border border-border-strong bg-surface-2 text-muted-foreground hover:bg-surface-3 hover:text-foreground",
          className,
        )}
      >
        {trigger === "avatar" ? (
          (user?.email?.[0]?.toUpperCase() ?? "?")
        ) : (
          <Settings className="h-4 w-4" aria-hidden="true" />
        )}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>{user?.full_name || user?.email}</DialogTitle>
            <DialogDescription className="capitalize">
              {user?.role} account
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4 border-y border-border py-3">
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Density
              </span>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={mode === "comfortable" ? "default" : "outline"}
                  aria-pressed={mode === "comfortable"}
                  onClick={() => setMode("comfortable")}
                >
                  Comfortable
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={mode === "compact" ? "default" : "outline"}
                  aria-pressed={mode === "compact"}
                  onClick={() => setMode("compact")}
                >
                  Compact
                </Button>
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Rendering
              </span>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={tier === "full" ? "default" : "outline"}
                  aria-pressed={tier === "full"}
                  onClick={() => setTier("full")}
                >
                  Full
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={tier === "lite" ? "default" : "outline"}
                  aria-pressed={tier === "lite"}
                  onClick={() => setTier("lite")}
                >
                  Lite
                </Button>
              </div>
            </div>
          </div>
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
    </>
  );
}
