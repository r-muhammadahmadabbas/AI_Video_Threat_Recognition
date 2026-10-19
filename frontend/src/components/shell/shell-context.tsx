"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";

export interface FeedIncident {
  id: number;
  event_type: string;
  severity: string;
  status: string;
  confidence: number;
  camera_id: number;
  first_seen_at: string;
}

interface ShellState {
  incidents: FeedIncident[];
  detectedCount: number;
  feedOpen: boolean;
  setFeedOpen: (open: boolean) => void;
  toggleFeed: () => void;
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  togglePalette: () => void;
}

const ShellContext = createContext<ShellState | null>(null);

export function ShellProvider({ children }: { children: ReactNode }) {
  const [incidents, setIncidents] = useState<FeedIncident[]>([]);
  const [feedOpen, setFeedOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      api
        .getIncidents({ limit: 25 })
        .then((data) => {
          if (cancelled) return;
          const list = Array.isArray(data) ? data : data.items;
          setIncidents(Array.isArray(list) ? (list as FeedIncident[]) : []);
        })
        .catch(() => {
          // feed is best-effort; keep last known items
        });
    };
    load();
    const timer = window.setInterval(load, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const detectedCount = incidents.filter(
    (incident) => incident.status === "detected",
  ).length;

  const value: ShellState = {
    incidents,
    detectedCount,
    feedOpen,
    setFeedOpen,
    toggleFeed: () => setFeedOpen((open) => !open),
    paletteOpen,
    setPaletteOpen,
    togglePalette: () => setPaletteOpen((open) => !open),
  };

  return (
    <ShellContext.Provider value={value}>{children}</ShellContext.Provider>
  );
}

export function useShell(): ShellState {
  const context = useContext(ShellContext);
  if (!context) throw new Error("useShell must be used within ShellProvider");
  return context;
}
