"use client";

import { useEffect, useSyncExternalStore } from "react";

export type DensityMode = "comfortable" | "compact";

const STORAGE_KEY = "display.density";
const listeners = new Set<() => void>();
let cached: DensityMode | null = null;

function getDensity(): DensityMode {
  if (cached === null) {
    try {
      cached =
        window.localStorage.getItem(STORAGE_KEY) === "compact"
          ? "compact"
          : "comfortable";
    } catch {
      cached = "comfortable";
    }
  }
  return cached;
}

function apply(mode: DensityMode): void {
  document.documentElement.dataset.density =
    mode === "compact" ? "compact" : "";
}

export function setDensity(mode: DensityMode): void {
  cached = mode;
  try {
    window.localStorage.setItem(STORAGE_KEY, mode);
  } catch {
    // storage unavailable — mode still applies for this session
  }
  apply(mode);
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useDensity(): {
  mode: DensityMode;
  setMode: (mode: DensityMode) => void;
} {
  const mode = useSyncExternalStore(
    subscribe,
    getDensity,
    () => "comfortable" as DensityMode,
  );
  useEffect(() => {
    apply(mode);
  }, [mode]);
  return { mode, setMode: setDensity };
}
