"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, X } from "lucide-react";
import { StatusBadge } from "@/components/status-badges";
import { useShell } from "@/components/shell/shell-context";
import { ruleLabel, severityInfo } from "@/lib/labels";
import { timeAgo } from "@/lib/time";
import { cn } from "@/lib/utils";

const SEVERITY_TEXT: Record<string, string> = {
  "sev-critical": "text-sev-critical",
  "sev-high": "text-sev-high",
  "sev-medium": "text-sev-medium",
  "sev-low": "text-sev-low",
  neutral: "text-muted-foreground",
};

export function IncidentFeed() {
  const router = useRouter();
  const { incidents, newCount, feedOpen, setFeedOpen } = useShell();

  return (
    <div
      aria-hidden={!feedOpen}
      className={cn(
        "fixed inset-0 z-40 md:left-auto md:top-14 md:w-[380px]",
        !feedOpen && "pointer-events-none",
      )}
    >
      <div
        onClick={() => setFeedOpen(false)}
        className={cn(
          "absolute inset-0 bg-black/50 transition-opacity duration-200 md:bg-transparent",
          feedOpen ? "opacity-100" : "opacity-0",
        )}
      />
      <aside
        aria-label="Incident feed"
        className={cn(
          "absolute inset-y-0 right-0 flex w-[88vw] max-w-sm flex-col border-l border-border bg-surface-1 transition-transform duration-200 ease-out-expo md:w-full md:max-w-none",
          feedOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4">
          <h2 className="text-sm font-semibold">Live feed</h2>
          {newCount > 0 && (
            <span className="rounded-full bg-sev-critical-bg px-2 py-0.5 text-[11px] font-semibold tabular-nums text-sev-critical">
              {newCount} new
            </span>
          )}
          <button
            type="button"
            onClick={() => setFeedOpen(false)}
            aria-label="Close feed"
            className="ml-auto rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-surface-3 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto">
          {incidents.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-muted-foreground">
              No recent incidents.
            </p>
          ) : (
            incidents.map((incident) => {
              const info = severityInfo(incident.severity);
              const Icon = info.icon;
              return (
                <button
                  key={incident.id}
                  type="button"
                  onClick={() => {
                    setFeedOpen(false);
                    router.push(`/incidents/${incident.id}`);
                  }}
                  className="w-full border-b border-border px-4 py-3 text-left transition-colors hover:bg-surface-2"
                >
                  <div className="flex items-center gap-2">
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        SEVERITY_TEXT[info.token] ?? SEVERITY_TEXT.neutral,
                      )}
                      aria-hidden="true"
                    />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">
                      {ruleLabel(incident.event_type)}
                    </span>
                    <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
                      {timeAgo(incident.first_seen_at)}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 pl-6">
                    <StatusBadge
                      status={incident.status}
                      className="px-1.5 py-0 text-[10px]"
                    />
                    <span className="text-[11px] text-muted-foreground">
                      Cam #{incident.camera_id} ·{" "}
                      {(incident.confidence * 100).toFixed(0)}%
                    </span>
                    <span className="ml-auto font-mono text-[11px] text-muted-foreground">
                      #{incident.id}
                    </span>
                  </div>
                </button>
              );
            })
          )}
        </div>

        <footer className="shrink-0 border-t border-border p-3">
          <Link
            href="/incidents"
            onClick={() => setFeedOpen(false)}
            className="flex items-center justify-center gap-2 rounded-md border border-border-strong bg-surface-2 px-3 py-2 text-sm font-medium transition-colors hover:bg-surface-3"
          >
            View all incidents
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </footer>
      </aside>
    </div>
  );
}
