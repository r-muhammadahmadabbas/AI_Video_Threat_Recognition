"use client";

import { RuleTrigger } from "@/types";
import { Badge } from "@/components/ui/badge";

interface RuleAlertProps {
  ruleTrigger: RuleTrigger;
}

const severityVariant: Record<
  string,
  "destructive" | "warning" | "secondary" | "info"
> = {
  critical: "destructive",
  very_high: "destructive",
  high: "destructive",
  medium: "warning",
  low: "info",
};

export function RuleAlert({ ruleTrigger }: RuleAlertProps) {
  return (
    <div className="flex flex-col gap-3 p-4 rounded-lg border border-border bg-background">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-white text-xs font-bold">
          !
        </span>
        <span className="font-medium">{ruleTrigger.rule}</span>
        <Badge variant={severityVariant[ruleTrigger.severity] ?? "secondary"}>
          {ruleTrigger.severity}
        </Badge>
      </div>
      <div className="text-sm text-foreground mt-1">
        <span className="font-medium">Triggered:</span>{" "}
        {ruleTrigger.timestamp.toFixed(1)}s
      </div>
      <div className="text-sm font-mono text-foreground">
        Track IDs: {ruleTrigger.tracker_ids.join(", ")}
      </div>
      <div className="mt-2 text-sm font-mono text-foreground">
        <span className="font-medium">Details:</span>
        <ul className="list-disc pl-4 text-xs text-muted-foreground">
          {Object.entries(ruleTrigger.details).map(([key, value]) => (
            <li key={key}>
              {key}:{" "}
              {typeof value === "object"
                ? JSON.stringify(value)
                : String(value)}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
