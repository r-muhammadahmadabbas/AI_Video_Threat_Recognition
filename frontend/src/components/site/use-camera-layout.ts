"use client";

import { useCallback, useMemo, useState } from "react";

export interface CameraPlacement {
  x: number;
  z: number;
  yaw: number;
}

export type CameraLayout = Record<number, CameraPlacement>;

export const LAYOUT_KEY = "siteTwin.layout.v1";
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const MAX_RADIUS = 14;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function autoLayout(cameraIds: number[]): CameraLayout {
  const layout: CameraLayout = {};
  cameraIds.forEach((id, index) => {
    const angle = index * GOLDEN_ANGLE;
    const radius = Math.min(MAX_RADIUS, 2.6 * Math.sqrt(index + 0.6));
    const x = Math.cos(angle) * radius;
    const z = Math.sin(angle) * radius;
    layout[id] = { x, z, yaw: angle + Math.PI };
  });
  return layout;
}

function loadLayout(): CameraLayout {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LAYOUT_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const layout: CameraLayout = {};
    for (const [key, value] of Object.entries(parsed)) {
      const id = Number(key);
      if (!Number.isFinite(id)) continue;
      const placement = value as Partial<CameraPlacement>;
      if (
        typeof placement?.x === "number" &&
        typeof placement?.z === "number" &&
        typeof placement?.yaw === "number"
      ) {
        layout[id] = {
          x: clamp(placement.x, -MAX_RADIUS, MAX_RADIUS),
          z: clamp(placement.z, -MAX_RADIUS, MAX_RADIUS),
          yaw: placement.yaw,
        };
      }
    }
    return layout;
  } catch {
    return {};
  }
}

function persist(layout: CameraLayout) {
  try {
    window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
  } catch {
    // storage unavailable — layout applies for this session only
  }
}

export function useCameraLayout(cameraIds: number[]) {
  const [saved, setSaved] = useState<CameraLayout>(() =>
    typeof window === "undefined" ? {} : loadLayout(),
  );

  const auto = useMemo(() => autoLayout(cameraIds), [cameraIds]);

  const layout = useMemo(() => {
    const merged: CameraLayout = {};
    for (const id of cameraIds) {
      merged[id] = saved[id] ?? auto[id];
    }
    return merged;
  }, [cameraIds, saved, auto]);

  const save = useCallback((id: number, placement: CameraPlacement) => {
    setSaved((previous) => {
      const next = { ...previous, [id]: placement };
      persist(next);
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setSaved({});
    try {
      window.localStorage.removeItem(LAYOUT_KEY);
    } catch {
      // ignore
    }
  }, []);

  return {
    layout,
    save,
    reset,
    hasSaved: Object.keys(saved).length > 0,
  };
}

export { MAX_RADIUS };
