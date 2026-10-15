"use client";

import { DetectionResult, RuleTrigger } from "@/types";
import { DetectionFrame } from "./DetectionFrame";
import { RuleAlert } from "./RuleAlert";

interface DetectionListProps {
  detections: DetectionResult[];
  events: RuleTrigger[];
}

export function DetectionList({ detections, events }: DetectionListProps) {
  return (
    <div className="flex flex-col gap-3">
      {events.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-red-500 mb-2">
            <span className="flex h-3 w-3 rounded-full bg-red-500" />
            Rule Alerts
          </div>
          <div className="space-y-2">
            {events.map((trigger) => (
              <RuleAlert
                key={`${trigger.rule}-${trigger.timestamp}`}
                ruleTrigger={trigger}
              />
            ))}
          </div>
        </div>
      )}
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-foreground mb-2">
          Detected Tracks ({detections.length})
        </div>
        {detections.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No detections found in this video.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {detections.map((detection, index) => (
              <DetectionFrame
                key={`${detection.track_id}-${detection.timestamp}-${index}`}
                detection={detection}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
