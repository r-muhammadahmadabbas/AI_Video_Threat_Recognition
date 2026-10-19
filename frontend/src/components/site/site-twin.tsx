"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { toast } from "sonner";
import type { Camera } from "@/types";
import { isWebGLAvailable, usePerfTier } from "@/lib/perf";
import { SiteMap2D } from "./site-map-2d";
import type { CameraLayout, CameraPlacement } from "./use-camera-layout";
import type { SitePing } from "./use-site-pings";

const SiteTwin3D = dynamic(
  () => import("./site-twin-3d").then((module) => module.SiteTwin3D),
  { ssr: false },
);

interface AlertIncident {
  id: number;
  camera_id: number;
  severity: string;
  status: string;
}

interface SiteTwinProps {
  cameras: Camera[];
  layout: CameraLayout;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  incidents: AlertIncident[];
  pings: SitePing[];
  listId: string;
  editable?: boolean;
  onMove?: (id: number, placement: CameraPlacement) => void;
  showSwitch?: boolean;
}

type View = "2d" | "3d";

const SEVERITY_RANK: Record<string, number> = {
  very_high: 4,
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

let webglSnapshot: boolean | null = null;

function getWebglSnapshot(): boolean {
  if (webglSnapshot === null) webglSnapshot = isWebGLAvailable();
  return webglSnapshot;
}

function subscribeWebgl(): () => void {
  return () => undefined;
}

export function SiteTwin({
  cameras,
  layout,
  selectedId,
  onSelect,
  incidents,
  pings,
  listId,
  editable = false,
  onMove,
  showSwitch = true,
}: SiteTwinProps) {
  const { tier } = usePerfTier();
  const webgl = useSyncExternalStore(
    subscribeWebgl,
    getWebglSnapshot,
    () => false,
  );
  const available = tier === "full" && webgl;

  const [manualView, setManualView] = useState<View | null>(null);
  const [idleReady, setIdleReady] = useState(false);

  useEffect(() => {
    if (!available) return;
    if (typeof window.requestIdleCallback === "function") {
      const idle = window.requestIdleCallback(() => setIdleReady(true), {
        timeout: 1500,
      });
      return () => window.cancelIdleCallback(idle);
    }
    const timer = window.setTimeout(() => setIdleReady(true), 200);
    return () => window.clearTimeout(timer);
  }, [available]);

  const autoView: View = available && idleReady ? "3d" : "2d";
  const view: View = editable ? "2d" : (manualView ?? autoView);

  const alertLevels = useMemo(() => {
    const levels: Record<number, string> = {};
    for (const incident of incidents) {
      if (
        incident.status !== "detected" &&
        incident.status !== "pending_review"
      ) {
        continue;
      }
      const rank = SEVERITY_RANK[incident.severity] ?? 0;
      if (rank < 3) continue;
      const current = levels[incident.camera_id];
      if (!current || rank > (SEVERITY_RANK[current] ?? 0)) {
        levels[incident.camera_id] = incident.severity;
      }
    }
    return levels;
  }, [incidents]);

  const choose = (next: View) => {
    if (next === "3d" && !available) {
      toast("3D is unavailable on this device — showing the 2D map.");
      return;
    }
    if (next === "3d") setIdleReady(true);
    setManualView(next);
  };

  const handleFallback = (reason: "performance" | "context") => {
    setManualView("2d");
    if (reason === "performance") {
      toast("Switched to the 2D map for performance.");
    } else {
      toast("3D view lost its graphics context — switched to the 2D map.");
    }
  };

  const mapProps = {
    cameras,
    layout,
    selectedId,
    onSelect,
    alertLevels,
    pings,
    editable,
    onMove,
    listId,
  };

  return (
    <div className="relative h-full w-full">
      {view === "3d" ? (
        <SiteTwin3D
          cameras={cameras}
          layout={layout}
          selectedId={selectedId}
          onSelect={onSelect}
          alertLevels={alertLevels}
          pings={pings}
          listId={listId}
          onFallback={handleFallback}
        />
      ) : (
        <SiteMap2D {...mapProps} />
      )}

      {showSwitch ? (
        <div
          className="absolute right-2 top-2 z-10 flex items-center gap-0.5 rounded-md border border-border bg-surface-1/95 p-0.5"
          role="group"
          aria-label="Map view"
        >
          {(["3d", "2d"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => choose(option)}
              aria-pressed={view === option}
              disabled={option === "3d" && (!available || editable)}
              title={
                option === "3d" && !available
                  ? "3D is unavailable on this device"
                  : option === "3d" && editable
                    ? "Switch to the 2D map to edit the layout"
                    : undefined
              }
              className={`rounded px-2 py-1 text-[11px] font-medium uppercase transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                view === option
                  ? "bg-surface-3 text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {option === "3d" ? "3D" : "2D"}
            </button>
          ))}
        </div>
      ) : null}

      {cameras.length === 0 ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="rounded-md border border-border bg-surface-1 px-3 py-2 text-sm text-muted-foreground">
            No cameras configured
          </p>
        </div>
      ) : null}
    </div>
  );
}
