"use client";

import { useCallback, useRef } from "react";
import type { Camera } from "@/types";
import { severityInfo } from "@/lib/labels";
import { useReducedMotionPref } from "@/hooks/use-reduced-motion-pref";
import type { CameraLayout, CameraPlacement } from "./use-camera-layout";
import type { SitePing } from "./use-site-pings";
import { MAX_RADIUS } from "./use-camera-layout";

interface SiteMap2DProps {
  cameras: Camera[];
  layout: CameraLayout;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  alertLevels: Record<number, string>;
  pings: SitePing[];
  editable?: boolean;
  onMove?: (id: number, placement: CameraPlacement) => void;
}

function severityVar(severity: string): string {
  const token = severityInfo(severity).token;
  return token === "neutral" ? "var(--muted-foreground)" : `var(--${token})`;
}

function clampScene(value: number): number {
  return Math.min(MAX_RADIUS, Math.max(-MAX_RADIUS, value));
}

export function SiteMap2D({
  cameras,
  layout,
  selectedId,
  onSelect,
  alertLevels,
  pings,
  editable = false,
  onMove,
}: SiteMap2DProps) {
  const reduced = useReducedMotionPref();
  const svgRef = useRef<SVGSVGElement>(null);
  const dragging = useRef<number | null>(null);

  const toScene = useCallback((event: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return null;
    const matrix = svg.getScreenCTM();
    if (!matrix) return null;
    const point = new DOMPoint(event.clientX, event.clientY);
    const scene = point.matrixTransform(matrix.inverse());
    return { x: clampScene(scene.x), z: clampScene(scene.y) };
  }, []);

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    if (!editable || dragging.current === null || !onMove) return;
    const scene = toScene(event);
    const id = dragging.current;
    if (!scene || !layout[id]) return;
    onMove(id, { ...layout[id], x: scene.x, z: scene.z });
  };

  const handlePointerUp = () => {
    dragging.current = null;
  };

  return (
    <div
      className="relative h-full w-full overflow-hidden rounded-md bg-background"
      aria-hidden="true"
    >
      <svg
        ref={svgRef}
        viewBox="-16 -16 32 32"
        preserveAspectRatio="xMidYMid meet"
        className={`h-full w-full ${editable ? "cursor-crosshair touch-none" : ""}`}
        data-testid="site-map-2d"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        <defs>
          <pattern
            id="site-grid"
            width="2"
            height="2"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 2 0 L 0 0 0 2"
              fill="none"
              stroke="var(--border)"
              strokeWidth="0.06"
            />
          </pattern>
        </defs>
        <rect x="-16" y="-16" width="32" height="32" fill="url(#site-grid)" />

        {cameras.map((camera) => {
          const placement = layout[camera.id];
          if (!placement) return null;
          const online = camera.status === "online";
          const alert = alertLevels[camera.id];
          const color = alert
            ? severityVar(alert)
            : online
              ? "var(--primary)"
              : "var(--muted-foreground)";
          const selected = camera.id === selectedId;
          const yawDegrees = (placement.yaw * 180) / Math.PI;

          return (
            <g
              key={camera.id}
              transform={`translate(${placement.x.toFixed(2)} ${placement.z.toFixed(2)}) rotate(${yawDegrees.toFixed(1)})`}
              className={editable ? "cursor-move" : "cursor-pointer"}
              onPointerDown={(event) => {
                if (editable && onMove) {
                  event.stopPropagation();
                  dragging.current = camera.id;
                  onSelect(camera.id);
                } else {
                  onSelect(camera.id);
                }
              }}
            >
              <path
                d="M0 0 L -2.4 6.4 L 2.4 6.4 Z"
                fill={color}
                opacity={online ? 0.16 : 0.08}
                stroke={color}
                strokeOpacity={online ? 0.45 : 0.2}
                strokeWidth="0.06"
              />
              {!online ? (
                <circle
                  r="1"
                  fill="none"
                  stroke="var(--muted-foreground)"
                  strokeWidth="0.08"
                  strokeDasharray="0.32 0.26"
                />
              ) : null}
              <circle
                r={selected ? 0.75 : 0.55}
                fill={color}
                stroke="var(--background)"
                strokeWidth="0.16"
              />
              {alert ? (
                <circle
                  r="1.25"
                  fill="none"
                  stroke={color}
                  strokeWidth="0.1"
                  opacity="0.8"
                />
              ) : null}
              {selected ? (
                <>
                  <circle
                    r="1.55"
                    fill="none"
                    stroke="var(--primary)"
                    strokeWidth="0.08"
                  />
                  <text
                    y="2.6"
                    textAnchor="middle"
                    fontSize="0.9"
                    fill="var(--foreground)"
                    transform={`rotate(${(-yawDegrees).toFixed(1)})`}
                  >
                    {camera.name}
                  </text>
                </>
              ) : null}
            </g>
          );
        })}

        {pings.map((ping) => {
          const placement = layout[ping.cameraId];
          if (!placement) return null;
          const color = severityVar(ping.severity);
          return (
            <circle
              key={`${ping.id}-${ping.cameraId}`}
              cx={placement.x}
              cy={placement.z}
              r="0.7"
              fill="none"
              stroke={color}
              strokeWidth="0.12"
              className={reduced ? undefined : "site-ping"}
              opacity={reduced ? 0.8 : undefined}
            />
          );
        })}
      </svg>
    </div>
  );
}
