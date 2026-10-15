"use client";

import { RuleTrigger } from "@/types";
import { Badge } from "@/components/ui/badge";

const severityVariant: Record<
  string,
  "destructive" | "warning" | "secondary" | "info"
> = {
  high: "destructive",
  medium: "warning",
  low: "info",
};

export function AltercationCard({ trigger }: { trigger: RuleTrigger }) {
  const distance = trigger.details?.distance;

  return (
    <div className="flex flex-col gap-3 p-4 rounded-lg border border-border bg-background">
      <div className="flex items-center gap-2">
        <span className="text-sm font-bold text-foreground">
          Track IDs: {trigger.tracker_ids.join(", ")}
        </span>
        <Badge variant={severityVariant[trigger.severity] ?? "secondary"}>
          {trigger.severity}
        </Badge>
      </div>
      {typeof distance === "number" && (
        <div className="flex justify-between items-start mt-2 text-sm text-foreground">
          <span className="font-medium">Distance:</span> {distance.toFixed(1)}{" "}
          px
        </div>
      )}
    </div>
  );
}

export default AltercationCard;
