"use client";

import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import type { Incident, IncidentListResponse } from "@/types";

export interface IncidentSeries {
  incidents: Incident[];
  total: number;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

const PAGE_SIZE = 100;
const PAGES = 2;

async function loadIncidentPages(): Promise<{
  incidents: Incident[];
  total: number;
}> {
  const pages = await Promise.all(
    Array.from(
      { length: PAGES },
      (_, index) =>
        api.getIncidents({
          page: index + 1,
          page_size: PAGE_SIZE,
        }) as Promise<IncidentListResponse>,
    ),
  );
  const incidents = pages.flatMap((page) => page.items ?? []);
  return { incidents, total: pages[0]?.total ?? incidents.length };
}

export function useIncidentSeries(): IncidentSeries {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await loadIncidentPages();
      setIncidents(result.incidents);
      setTotal(result.total);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not load incident data"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadIncidentPages()
      .then((result) => {
        if (cancelled) return;
        setIncidents(result.incidents);
        setTotal(result.total);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(apiErrorMessage(err, "Could not load incident data"));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { incidents, total, loading, error, refetch };
}

export const SEVERITY_KEYS = ["critical", "high", "medium", "low"] as const;
export type SeverityKey = (typeof SEVERITY_KEYS)[number];

export type SeverityCounts = Record<SeverityKey, number>;

export function severityCounts(incidents: Incident[]): SeverityCounts {
  const counts: SeverityCounts = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const incident of incidents) {
    const key = incident.severity as SeverityKey;
    if (key === "critical" || key === "high" || key === "medium") {
      counts[key] += 1;
    } else {
      counts.low += 1;
    }
  }
  return counts;
}

export interface TrendPoint extends SeverityCounts {
  label: string;
}

export type TrendMode = "24h" | "7d";

function addToBucket(bucket: TrendPoint, severity: string) {
  if (severity === "critical" || severity === "high" || severity === "medium") {
    bucket[severity] += 1;
  } else {
    bucket.low += 1;
  }
}

export function buildTrend(
  incidents: Incident[],
  mode: TrendMode,
): TrendPoint[] {
  const now = new Date();

  if (mode === "24h") {
    const start = new Date(now);
    start.setMinutes(0, 0, 0);
    start.setHours(start.getHours() - 23);
    const buckets: TrendPoint[] = Array.from({ length: 24 }, (_, index) => {
      const hour = new Date(start);
      hour.setHours(start.getHours() + index);
      return {
        label: hour.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
      };
    });
    for (const incident of incidents) {
      const time = new Date(incident.first_seen_at).getTime();
      const index = Math.floor((time - start.getTime()) / 3_600_000);
      if (index >= 0 && index < buckets.length) {
        addToBucket(buckets[index], incident.severity);
      }
    }
    return buckets;
  }

  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - 6);
  const buckets: TrendPoint[] = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return {
      label: day.toLocaleDateString([], { month: "short", day: "numeric" }),
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    };
  });
  for (const incident of incidents) {
    const time = new Date(incident.first_seen_at);
    const index = Math.floor(
      (new Date(time).setHours(0, 0, 0, 0) - start.getTime()) / 86_400_000,
    );
    if (index >= 0 && index < buckets.length) {
      addToBucket(buckets[index], incident.severity);
    }
  }
  return buckets;
}

export function buildSparkline(incidents: Incident[]): number[] {
  return buildTrend(incidents, "24h").map(
    (bucket) => bucket.critical + bucket.high + bucket.medium + bucket.low,
  );
}
