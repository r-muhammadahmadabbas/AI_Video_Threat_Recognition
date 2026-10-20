import { cn } from "@/lib/utils";
import { severityInfo, statusInfo } from "@/lib/labels";

const TOKEN_CLASSES: Record<string, string> = {
  "sev-critical": "border-sev-critical/40 bg-sev-critical-bg text-sev-critical",
  "sev-high": "border-sev-high/40 bg-sev-high-bg text-sev-high",
  "sev-medium": "border-sev-medium/40 bg-sev-medium-bg text-sev-medium",
  "sev-low": "border-sev-low/40 bg-sev-low-bg text-sev-low",
  ok: "border-ok/40 bg-ok-bg text-ok",
  warning: "border-sev-medium/40 bg-sev-medium-bg text-sev-medium",
  critical: "border-sev-critical/40 bg-sev-critical-bg text-sev-critical",
  info: "border-sev-low/40 bg-sev-low-bg text-sev-low",
  neutral: "border-border-strong bg-surface-2 text-muted-foreground",
};

const BADGE_BASE =
  "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold";

export function SeverityBadge({
  severity,
  className,
}: {
  severity: string;
  className?: string;
}) {
  const info = severityInfo(severity);
  const Icon = info.icon;
  return (
    <span
      className={cn(
        BADGE_BASE,
        TOKEN_CLASSES[info.token] ?? TOKEN_CLASSES.neutral,
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {info.label}
    </span>
  );
}

export function StatusBadge({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  const info = statusInfo(status);
  const Icon = info.icon;
  return (
    <span
      className={cn(
        BADGE_BASE,
        TOKEN_CLASSES[info.token] ?? TOKEN_CLASSES.neutral,
        className,
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {info.label}
    </span>
  );
}
