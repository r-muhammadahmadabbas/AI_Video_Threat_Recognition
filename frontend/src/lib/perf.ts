"use client";

import { useEffect, useSyncExternalStore } from "react";

export type PerfTier = "full" | "lite";

const STORAGE_KEY = "perf.mode";
const listeners = new Set<() => void>();
let cached: PerfTier | null = null;

function probeWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const gl = (canvas.getContext("webgl2") ??
      canvas.getContext("webgl")) as WebGLRenderingContext | null;
    if (!gl) return false;
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

function detectTier(): PerfTier {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "full" || stored === "lite") return stored;
  const nav = navigator as Navigator & {
    connection?: { saveData?: boolean };
    deviceMemory?: number;
  };
  if (nav.connection?.saveData) return "lite";
  if ((nav.deviceMemory ?? 8) <= 4) return "lite";
  if ((nav.hardwareConcurrency ?? 8) <= 4) return "lite";
  if (!probeWebGL()) return "lite";
  return "full";
}

export function getPerfTier(): PerfTier {
  if (cached === null) cached = detectTier();
  return cached;
}

export function setPerfTier(tier: PerfTier): void {
  cached = tier;
  try {
    window.localStorage.setItem(STORAGE_KEY, tier);
  } catch {
    // storage unavailable — tier still applies for this session
  }
  document.documentElement.dataset.perf = tier;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function usePerfTier(): {
  tier: PerfTier;
  setTier: (t: PerfTier) => void;
} {
  const tier = useSyncExternalStore(
    subscribe,
    getPerfTier,
    () => "full" as PerfTier,
  );
  useEffect(() => {
    document.documentElement.dataset.perf = tier;
  }, [tier]);
  return { tier, setTier: setPerfTier };
}
