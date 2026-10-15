"use client";

import { DetectionResult } from "@/types";
import { classInfo } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";

interface DetectionFrameProps {
  detection: DetectionResult;
}

export function DetectionFrame({ detection }: DetectionFrameProps) {
  const info = classInfo(detection.class_name);
  const flags = [
    detection.weapon
      ? `weapon ${(detection.weapon_conf * 100).toFixed(0)}%`
      : null,
    detection.fall ? "fall" : null,
    detection.violence ? "violence" : null,
  ].filter(Boolean);

  return (
    <div className="flex flex-col gap-3">
      <div className="relative group aspect-[4/3] overflow-hidden rounded-xl border border-border bg-background">
        {detection.frame_image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={`data:image/jpeg;base64,${detection.frame_image}`}
            alt={`${info.label} at ${detection.timestamp}s`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
            No frame available
          </div>
        )}
        <div className="absolute left-2 top-2 rounded bg-black/60 px-2 py-1 font-mono text-xs text-white">
          t={detection.timestamp}s
        </div>
      </div>
      <div className="flex items-center justify-between gap-4 px-2 text-sm">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="truncate text-sm font-medium">{info.label}</span>
          <span className="text-xs text-muted-foreground">
            Confidence: {(detection.confidence * 100).toFixed(1)}%
            {flags.length > 0 && ` · ${flags.join(", ")}`}
          </span>
        </div>
        <Badge variant={detection.is_threat ? "destructive" : "secondary"}>
          {detection.is_threat ? info.short : "Clear"}
        </Badge>
      </div>
    </div>
  );
}
