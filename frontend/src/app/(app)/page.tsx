"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle,
  Radio,
  ScanSearch,
  ShieldAlert,
  Video,
  Wifi,
  WifiOff,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  Camera,
  DashboardStats,
  IncidentListResponse,
  Paginated,
} from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { SeverityBadge, StatusBadge } from "@/components/status-badges";
import { EmptyState, ErrorState } from "@/components/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

function StatCard({
  title,
  value,
  icon: Icon,
  accent,
}: {
  title: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-6">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="mt-1 text-3xl font-bold">{value}</p>
        </div>
        <div className={`rounded-lg bg-accent/60 p-3 ${accent}`}>
          <Icon className="h-6 w-6" />
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const {
    data: stats,
    loading,
    error,
    refetch,
  } = useFetch<DashboardStats>(() => api.getDashboardStats(), []);

  const [cameras, setCameras] = useState<Camera[]>([]);
  const [incidents, setIncidents] = useState<IncidentListResponse | null>(null);

  useEffect(() => {
    api
      .getCameras({ page_size: 5 })
      .then((data: Paginated<Camera>) => setCameras(data.items ?? []))
      .catch(() => setCameras([]));
    api
      .getIncidents({ page_size: 5 })
      .then((data: IncidentListResponse) => setIncidents(data))
      .catch(() => setIncidents(null));
  }, []);

  useEffect(() => {
    const interval = setInterval(refetch, 30000);
    return () => clearInterval(interval);
  }, [refetch]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            System overview and key metrics
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href="/live">
              <Radio className="h-4 w-4" />
              Live Stream
            </Link>
          </Button>
          <Button asChild>
            <Link href="/detect">
              <ScanSearch className="h-4 w-4" />
              New Detection
            </Link>
          </Button>
        </div>
      </div>

      {error && <ErrorState message={error} />}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {loading ? (
          Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-28" />
          ))
        ) : (
          <>
            <StatCard
              title="Total Cameras"
              value={stats?.total_cameras ?? 0}
              icon={Video}
              accent="text-blue-500"
            />
            <StatCard
              title="Online Cameras"
              value={stats?.online_cameras ?? 0}
              icon={CheckCircle}
              accent="text-green-500"
            />
            <StatCard
              title="Total Incidents"
              value={stats?.total_incidents ?? 0}
              icon={AlertTriangle}
              accent="text-amber-500"
            />
            <StatCard
              title="Pending Review"
              value={stats?.pending_incidents ?? 0}
              icon={ScanSearch}
              accent="text-blue-500"
            />
            <StatCard
              title="Very High Risk"
              value={stats?.very_high_risk_incidents ?? 0}
              icon={ShieldAlert}
              accent="text-red-500"
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">Cameras</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/cameras">View all</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {cameras.length === 0 ? (
              <EmptyState
                title="No cameras configured"
                description="Add a camera to start monitoring zones and rules."
                icon={Video}
              />
            ) : (
              <ul className="divide-y divide-border">
                {cameras.map((camera) => {
                  const online = camera.status === "online";
                  return (
                    <li
                      key={camera.id}
                      className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
                    >
                      {online ? (
                        <Wifi className="h-4 w-4 text-green-500" />
                      ) : (
                        <WifiOff className="h-4 w-4 text-red-500" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                          {camera.name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {camera.source_type?.toUpperCase()} ·{" "}
                          {online ? "Online" : "Offline"}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">Recent Incidents</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/incidents">View all</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {!incidents || incidents.items.length === 0 ? (
              <EmptyState
                title="No incidents yet"
                description="Detected threats will appear here for review."
                icon={AlertTriangle}
              />
            ) : (
              <ul className="divide-y divide-border">
                {incidents.items.map((incident) => (
                  <li
                    key={incident.id}
                    className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <Link
                      href={`/incidents/${incident.id}`}
                      className="min-w-0 flex-1"
                    >
                      <p className="truncate text-sm font-medium capitalize">
                        {incident.event_type.replace(/_/g, " ")}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(incident.first_seen_at).toLocaleString()}
                      </p>
                    </Link>
                    <div className="flex shrink-0 items-center gap-2">
                      <SeverityBadge severity={incident.severity} />
                      <StatusBadge status={incident.status} />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
