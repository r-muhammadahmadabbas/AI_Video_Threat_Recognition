"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(listener: () => void): () => void {
  const mql = window.matchMedia(QUERY);
  mql.addEventListener("change", listener);
  return () => mql.removeEventListener("change", listener);
}

function getSnapshot(): boolean {
  return window.matchMedia(QUERY).matches;
}

export function useReducedMotionPref(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
