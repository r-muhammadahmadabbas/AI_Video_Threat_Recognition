"use client";

import { useMemo, useState } from "react";
import { Activity, Crosshair, Film, ShieldAlert, Timer } from "lucide-react";
import { DetectionResponse } from "@/types";
import { classInfo, ruleLabel, severityVariant } from "@/lib/labels";
import { Badge } from "@/components/ui/badge";
import { DetectionFrame } from "./DetectionFrame";
import { DetectionTimeline } from "./DetectionTimeline";
import { cn } from "@/lib/utils";

export function AnalysisReport({ result }: { result: DetectionResponse }) {
  const [selected, setSelected] = useState<number | null>(null);

  const threats = result.detections.filter((d) => d.is_threat);
  const weaponThreats = result.detections.filter(
    (d) => d.weapon || classInfo(d.class_name).category === "Weapon",
  );

  const findings = useMemo(() => {
    const map = new Map<
      string,
      {
        class_name: string;
        count: number;
        maxConfidence: number;
        first: number;
        last: number;
        threat: boolean;
      }
    >();
    for (const detection of result.detections) {
      const info = classInfo(detection.class_name);
      const existing = map.get(detection.class_name);
      if (existing) {
        existing.count += 1;
        existing.maxConfidence = Math.max(
          existing.maxConfidence,
          detection.confidence,
        );
        existing.first = Math.min(existing.first, detection.timestamp);
        existing.last = Math.max(existing.last, detection.timestamp);
      } else {
        map.set(detection.class_name, {
          class_name: detection.class_name,
          count: 1,
          maxConfidence: detection.confidence,
          first: detection.timestamp,
          last: detection.timestamp,
          threat: info.threat || detection.is_threat,
        });
      }
    }
    return [...map.values()].sort((a, b) => {
      if (a.threat !== b.threat) return a.threat ? -1 : 1;
      return b.maxConfidence - a.maxConfidence;
    });
  }, [result.detections]);

  const stats = [
    {
      label: "Frames analyzed",
      value: result.total_frames,
      icon: Film,
      accent: "text-muted-foreground",
    },
    {
      label: "Objects detected",
      value: result.detections.length,
      icon: Crosshair,
      accent: "text-blue-500",
    },
    {
      label: "Threats",
      value: threats.length,
      icon: ShieldAlert,
      accent: threats.length ? "text-red-500" : "text-muted-foreground",
    },
    {
      label: "Rule events",
      value: result.events.length,
      icon: Activity,
      accent: result.events.length ? "text-amber-500" : "text-muted-foreground",
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="flex items-center gap-3 rounded-lg border border-border bg-card p-4"
          >
            <stat.icon className={cn("h-5 w-5", stat.accent)} />
            <div>
              <div className="text-xl font-bold leading-none">{stat.value}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {stat.label}
              </div>
            </div>
          </div>
        ))}
      </div>

      {weaponThreats.length > 0 && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 font-semibold text-red-600">
            <ShieldAlert className="h-5 w-5" />
            Weapon identified
          </div>
          <ul className="mt-2 space-y-1 text-sm text-red-700">
            {weaponThreats.map((detection, index) => {
              const info = classInfo(detection.class_name);
              return (
                <li key={`${detection.timestamp}-${index}`}>
                  <span className="font-medium">{info.label}</span> detected at{" "}
                  <span className="font-mono">
                    t={detection.timestamp.toFixed(1)}s
                  </span>{" "}
                  (confidence {(detection.confidence * 100).toFixed(1)}%)
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {result.detections.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
            <Timer className="h-4 w-4 text-muted-foreground" />
            Detection timeline
          </div>
          <DetectionTimeline
            result={result}
            selected={selected}
            onSelect={setSelected}
          />
        </div>
      )}

      {findings.length > 0 && (
        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 text-sm font-semibold">
            Findings summary
          </div>
          <ul className="divide-y divide-border">
            {findings.map((finding) => {
              const info = classInfo(finding.class_name);
              return (
                <li
                  key={finding.class_name}
                  className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <Badge variant={info.threat ? "destructive" : "secondary"}>
                      {info.category}
                    </Badge>
                    <div>
                      <div className="text-sm font-medium">{info.label}</div>
                      <div className="text-xs text-muted-foreground">
                        {finding.count} observation
                        {finding.count > 1 ? "s" : ""} between{" "}
                        {finding.first.toFixed(1)}s and{" "}
                        {finding.last.toFixed(1)}s
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold">
                      {(finding.maxConfidence * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-muted-foreground">
                      max confidence
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {result.events.length > 0 && (
        <div className="rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3 text-sm font-semibold">
            Rule triggers
          </div>
          <ul className="divide-y divide-border">
            {result.events.map((event, index) => (
              <li
                key={`${event.rule}-${event.timestamp}-${index}`}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <Badge
                    variant={severityVariant(event.severity)}
                    className="capitalize"
                  >
                    {event.severity}
                  </Badge>
                  <div>
                    <div className="text-sm font-medium">
                      {ruleLabel(event.rule)}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      at {event.timestamp.toFixed(1)}s · tracks{" "}
                      {event.tracker_ids.join(", ") || "n/a"}
                    </div>
                  </div>
                </div>
                {Object.keys(event.details).length > 0 && (
                  <span className="font-mono text-[11px] text-muted-foreground">
                    {JSON.stringify(event.details).slice(0, 80)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.detections.length > 0 && (
        <div>
          <div className="mb-3 text-sm font-semibold">
            Annotated frames ({result.detections.length})
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {result.detections.map((detection, index) => (
              <button
                type="button"
                key={`${detection.track_id}-${detection.timestamp}-${index}`}
                onClick={() => setSelected(selected === index ? null : index)}
                className={cn(
                  "rounded-xl text-left transition-shadow",
                  selected === index &&
                    "ring-2 ring-primary ring-offset-2 ring-offset-background",
                )}
              >
                <DetectionFrame detection={detection} />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
