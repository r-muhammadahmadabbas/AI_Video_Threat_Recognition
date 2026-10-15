"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type SystemStatus = "checking" | "nominal" | "offline";

const STATUS_META: Record<SystemStatus, { dot: string; label: string }> = {
  checking: { dot: "bg-sev-medium", label: "Checking systems" },
  nominal: { dot: "bg-ok", label: "Systems nominal" },
  offline: { dot: "bg-sev-critical", label: "API offline" },
};

export function StatusPill() {
  const [status, setStatus] = useState<SystemStatus>("checking");

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      api
        .healthCheck()
        .then(() => {
          if (!cancelled) setStatus("nominal");
        })
        .catch(() => {
          if (!cancelled) setStatus("offline");
        });
    };
    const initial = window.setTimeout(check, 0);
    const timer = window.setInterval(check, 30000);
    return () => {
      cancelled = true;
      window.clearTimeout(initial);
      window.clearInterval(timer);
    };
  }, []);

  const meta = STATUS_META[status];

  return (
    <span className="hidden items-center gap-2 rounded-full border border-border-strong bg-surface-2 px-3 py-1 text-xs text-muted-foreground sm:inline-flex">
      <span
        className={cn("h-2 w-2 rounded-full", meta.dot)}
        aria-hidden="true"
      />
      {meta.label}
    </span>
  );
}
