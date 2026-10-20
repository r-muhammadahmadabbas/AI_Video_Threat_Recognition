"use client";

import { useMemo } from "react";
import { DetectionResponse } from "@/types";
import { classInfo, ruleLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

interface DetectionTimelineProps {
  result: DetectionResponse;
  selected: number | null;
  onSelect: (index: number | null) => void;
}

export function DetectionTimeline({
  result,
  selected,
  onSelect,
}: DetectionTimelineProps) {
  const duration = useMemo(() => {
    const stamps = [
      ...result.detections.map((d) => d.timestamp),
      ...result.events.map((e) => e.timestamp),
    ];
    return stamps.length ? Math.max(...stamps) + 0.5 : 1;
  }, [result]);

  return (
    <div className="w-full">
      <div className="relative mx-3 h-10">
        <div className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-border" />
        {result.detections.map((detection, index) => {
          const info = classInfo(detection.class_name);
          const left = Math.min(100, (detection.timestamp / duration) * 100);
          const isSelected = selected === index;
          return (
            <button
              key={`${detection.track_id}-${detection.timestamp}-${index}`}
              type="button"
              title={`${info.label} at ${detection.timestamp.toFixed(1)}s (${(detection.confidence * 100).toFixed(0)}%)`}
              onClick={() => onSelect(isSelected ? null : index)}
              className={cn(
                "absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-background transition-transform hover:scale-150",
                info.threat ? "bg-red-500" : "bg-blue-500",
                isSelected && "scale-150 ring-primary",
              )}
              style={{ left: `${left}%` }}
            />
          );
        })}
        {result.events.map((event, index) => {
          const left = Math.min(100, (event.timestamp / duration) * 100);
          return (
            <span
              key={`${event.rule}-${event.timestamp}-${index}`}
              title={`${ruleLabel(event.rule)} at ${event.timestamp.toFixed(1)}s`}
              className="absolute bottom-0 h-2 w-2 -translate-x-1/2 rotate-45 bg-red-600"
              style={{ left: `${left}%` }}
            />
          );
        })}
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>0s</span>
        <span>{duration.toFixed(1)}s</span>
      </div>
    </div>
  );
}
