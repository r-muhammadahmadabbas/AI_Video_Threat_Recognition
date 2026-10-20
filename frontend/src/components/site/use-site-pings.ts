"use client";

import { useEffect, useRef, useState } from "react";

export interface SitePing {
  id: number;
  cameraId: number;
  severity: string;
}

interface PingIncident {
  id: number;
  camera_id: number;
  severity: string;
}

const PING_LIFETIME_MS = 3000;
const MAX_PINGS = 5;

export function useSitePings(
  incidents: PingIncident[],
  enabled = true,
): SitePing[] {
  const [pings, setPings] = useState<SitePing[]>([]);
  const seen = useRef<Set<number> | null>(null);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    if (!enabled) return;
    if (seen.current === null) {
      seen.current = new Set(incidents.map((incident) => incident.id));
      return;
    }
    const fresh = incidents.filter(
      (incident) => !seen.current?.has(incident.id),
    );
    if (fresh.length === 0) return;
    for (const incident of fresh) seen.current.add(incident.id);
    const newPings = fresh.slice(0, MAX_PINGS).map((incident) => ({
      id: incident.id,
      cameraId: incident.camera_id,
      severity: incident.severity,
    }));
    setPings((previous) => [...previous, ...newPings].slice(-MAX_PINGS));
    const timer = window.setTimeout(() => {
      const ids = new Set(newPings.map((ping) => ping.id));
      setPings((previous) => previous.filter((ping) => !ids.has(ping.id)));
    }, PING_LIFETIME_MS);
    timers.current.push(timer);
  }, [incidents, enabled]);

  useEffect(() => {
    const list = timers.current;
    return () => {
      for (const timer of list) window.clearTimeout(timer);
    };
  }, []);

  return enabled ? pings : [];
}
