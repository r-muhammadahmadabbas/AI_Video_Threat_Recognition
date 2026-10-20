"use client";

import { useSyncExternalStore } from "react";

export interface ChartColors {
  critical: string;
  high: string;
  medium: string;
  low: string;
  primary: string;
  ok: string;
  foreground: string;
  muted: string;
  border: string;
  surface2: string;
}

const FALLBACKS: ChartColors = {
  critical: "oklch(0.66 0.22 25)",
  high: "oklch(0.74 0.17 55)",
  medium: "oklch(0.84 0.14 92)",
  low: "oklch(0.74 0.11 240)",
  primary: "oklch(0.8 0.13 205)",
  ok: "oklch(0.78 0.16 150)",
  foreground: "oklch(0.96 0.005 260)",
  muted: "oklch(0.72 0.02 260)",
  border: "oklch(1 0 0 / 0.08)",
  surface2: "oklch(0.225 0.016 260)",
};

let cached: ChartColors | null = null;

function readColors(): ChartColors {
  if (cached) return cached;
  const styles = getComputedStyle(document.documentElement);
  const read = (token: string, fallback: string) =>
    styles.getPropertyValue(token).trim() || fallback;
  cached = {
    critical: read("--sev-critical", FALLBACKS.critical),
    high: read("--sev-high", FALLBACKS.high),
    medium: read("--sev-medium", FALLBACKS.medium),
    low: read("--sev-low", FALLBACKS.low),
    primary: read("--primary", FALLBACKS.primary),
    ok: read("--ok", FALLBACKS.ok),
    foreground: read("--foreground", FALLBACKS.foreground),
    muted: read("--muted-foreground", FALLBACKS.muted),
    border: read("--border", FALLBACKS.border),
    surface2: read("--surface-2", FALLBACKS.surface2),
  };
  return cached;
}

function subscribe(): () => void {
  return () => undefined;
}

export function useChartColors(): ChartColors {
  return useSyncExternalStore(subscribe, readColors, () => FALLBACKS);
}
