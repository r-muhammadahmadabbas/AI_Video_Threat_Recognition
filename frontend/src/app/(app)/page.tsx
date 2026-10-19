"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo } from "react";
import {
  AlertTriangle,
  Clock,
  MapPin,
  Radio,
  ScanSearch,
  ShieldAlert,
  Video,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Camera, DashboardStats, Paginated } from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { useShell } from "@/components/shell/shell-context";
import { eventInfo, ruleLabel } from "@/lib/labels";
import { timeAgo } from "@/lib/time";
import { SeverityBadge, StatusBadge } from "@/components/status-badges";
import { StatusDot } from "@/components/status-dot";
import { EmptyState, ErrorState } from "@/components/empty-state";
import { KpiTile } from "@/components/dashboard/kpi-tile";
import { SiteTwinWidget } from "@/components/dashboard/site-twin-widget";
import {
  buildSparkline,
  useIncidentSeries,
} from "@/components/charts/use-incident-series";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

const TrendChart = dynamic(
  () =>
    import("@/components/charts/trend-chart").then(
      (module) => module.TrendChart,
    ),
  {
    ssr: false,
    loading: () => (
      <Card className="h-full">
        <CardContent className="p-5">
          <Skeleton className="h-72" />
        </CardContent>
      </Card>
    ),
  },
);

const SeverityDonut = dynamic(
  () =>
    import("@/components/charts/severity-donut").then(
      (module) => module.SeverityDonut,
    ),
  {
    ssr: false,
    loading: () => (
      <Card className="h-full">
        <CardContent className="p-5">
          <Skeleton className="h-56" />
        </CardContent>
      </Card>
    ),
  },
);

const ClassBars = dynamic(
  () =>
    import("@/components/charts/class-bars").then((module) => module.ClassBars),
  {
    ssr: false,
    loading: () => (
      <Card className="h-full">
        <CardContent className="p-5">
          <Skeleton className="h-56" />
        </CardContent>
      </Card>
    ),
  },
);

export default function DashboardPage() {
  const {
    data: stats,
    loading,
    error,
    refetch,
  } = useFetch<DashboardStats>(() => api.getDashboardStats(), []);

  const {
    data: camerasData,
    loading: camerasLoading,
    error: camerasError,
    refetch: refetchCameras,
  } = useFetch<Paginated<Camera>>(() => api.getCameras({ page_size: 100 }), []);

  const series = useIncidentSeries();
  const { refetch: refetchSeries } = series;
  const { incidents: feedIncidents } = useShell();

  useEffect(() => {
    const timer = window.setInterval(() => {
      refetch();
      refetchCameras();
      refetchSeries();
    }, 30000);
    return () => window.clearInterval(timer);
  }, [refetch, refetchCameras, refetchSeries]);

  const cameras = useMemo(() => {
    const items = camerasData?.items ?? [];
    return [...items].sort((a, b) => {
      const aOnline = a.status === "online" ? 1 : 0;
      const bOnline = b.status === "online" ? 1 : 0;
      if (aOnline !== bOnline) return aOnline - bOnline;
      return a.name.localeCompare(b.name);
    });
  }, [camerasData]);

  const cameraNames = useMemo(() => {
    const names = new Map<number, string>();
    for (const camera of cameras) names.set(camera.id, camera.name);
    return names;
  }, [cameras]);

  const spark = useMemo(
    () => buildSparkline(series.incidents),
    [series.incidents],
  );

  const lastIncident = series.incidents[0];
  const pending = stats?.pending_incidents ?? 0;
  const caption =
    series.total > series.incidents.length
      ? `Based on the latest ${series.incidents.length} of ${series.total} incidents`
      : `Based on the latest ${series.incidents.length} incidents`;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            System overview and key metrics
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline" className="gap-1.5">
            <Link href="/live">
              <Radio className="h-4 w-4" aria-hidden="true" />
              Live stream
            </Link>
          </Button>
          <Button asChild variant="outline" className="gap-1.5">
            <Link href="/site">
              <MapPin className="h-4 w-4" aria-hidden="true" />
              Site map
            </Link>
          </Button>
          <Button asChild className="gap-1.5">
            <Link href="/detect">
              <ScanSearch className="h-4 w-4" aria-hidden="true" />
              New detection
            </Link>
          </Button>
        </div>
      </div>

      {error ? <ErrorState message={error} /> : null}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {loading && !stats ? (
          Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-32" />
          ))
        ) : (
          <>
            <KpiTile
              label="Cameras"
              icon={Video}
              valueText={`${stats?.online_cameras ?? 0}/${stats?.total_cameras ?? 0}`}
              ring={{
                value: stats?.online_cameras ?? 0,
                total: stats?.total_cameras ?? 0,
              }}
              href="/cameras"
              footer={
                <p className="text-xs text-muted-foreground">online / total</p>
              }
            />
            <KpiTile
              label="Pending"
              icon={Clock}
              value={pending}
              featured
              tone={pending > 0 ? "critical" : "ok"}
              allClear={pending === 0}
              href="/incidents"
              footer={
                pending === 0 && lastIncident ? (
                  <p className="text-xs text-muted-foreground">
                    Last incident {timeAgo(lastIncident.first_seen_at)}
                  </p>
                ) : pending > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Awaiting review
                  </p>
                ) : null
              }
            />
            <KpiTile
              label="High risk"
              icon={ShieldAlert}
              value={stats?.very_high_risk_incidents ?? 0}
              tone="warning"
              href="/incidents"
              footer={
                <p className="text-xs text-muted-foreground">
                  critical or high, open
                </p>
              }
            />
            <KpiTile
              label="Last 24h"
              icon={AlertTriangle}
              value={stats?.incidents_last_24h ?? 0}
              spark={spark}
              footer={
                <p className="text-xs text-muted-foreground">new incidents</p>
              }
            />
            <KpiTile
              label="Verified"
              icon={ShieldAlert}
              value={stats?.verified_incidents ?? 0}
              tone="ok"
              footer={<p className="text-xs text-muted-foreground">all time</p>}
            />
            <KpiTile
              label="Dismissed"
              icon={AlertTriangle}
              value={stats?.dismissed_incidents ?? 0}
              footer={<p className="text-xs text-muted-foreground">all time</p>}
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <TrendChart
            incidents={series.incidents}
            loading={series.loading}
            error={series.error}
            onRetry={series.refetch}
            caption={caption}
          />
        </div>
        <div className="lg:col-span-4">
          <SiteTwinWidget cameras={cameras} incidents={feedIncidents} />
        </div>
        <div className="lg:col-span-4">
          <SeverityDonut
            incidents={series.incidents}
            loading={series.loading}
            error={series.error}
            onRetry={series.refetch}
          />
        </div>
        <div className="lg:col-span-4">
          <ClassBars
            incidents={series.incidents}
            loading={series.loading}
            error={series.error}
            onRetry={series.refetch}
          />
        </div>
        <div className="lg:col-span-4">
          <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base">Camera health</CardTitle>
              <Button asChild variant="ghost" size="sm">
                <Link href="/cameras">View all</Link>
              </Button>
            </CardHeader>
            <CardContent>
              {camerasError ? (
                <ErrorState message={camerasError} />
              ) : camerasLoading && cameras.length === 0 ? (
                <div className="flex flex-col gap-2">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <Skeleton key={index} className="h-9" />
                  ))}
                </div>
              ) : cameras.length === 0 ? (
                <EmptyState
                  title="No cameras configured"
                  description="Add a camera to start monitoring zones and rules."
                  icon={Video}
                />
              ) : (
                <ul className="divide-y divide-border">
                  {cameras.slice(0, 8).map((camera) => {
                    const isOnline = camera.status === "online";
                    return (
                      <li
                        key={camera.id}
                        className="flex items-center gap-2.5 py-2 first:pt-0 last:pb-0"
                      >
                        <StatusDot online={isOnline} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm">{camera.name}</p>
                          <p className="text-[11px] text-muted-foreground">
                            {isOnline ? "Online" : "Offline"}
                            {camera.inference_enabled
                              ? ` · inference ${camera.inference_fps ?? "—"} fps`
                              : " · inference off"}
                          </p>
                        </div>
                        <span className="text-[11px] uppercase text-muted-foreground">
                          {camera.source_type}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-12">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base">Live incident feed</CardTitle>
              <Button asChild variant="ghost" size="sm">
                <Link href="/incidents">View all</Link>
              </Button>
            </CardHeader>
            <CardContent>
              {series.loading && series.incidents.length === 0 ? (
                <div className="flex flex-col gap-2">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <Skeleton key={index} className="h-11" />
                  ))}
                </div>
              ) : series.incidents.length === 0 ? (
                <EmptyState
                  title="No incidents yet"
                  description="Detected threats will appear here for review."
                  icon={AlertTriangle}
                />
              ) : (
                <ul className="divide-y divide-border">
                  {series.incidents.slice(0, 8).map((incident) => {
                    const Icon = eventInfo(incident.event_type).icon;
                    return (
                      <li key={incident.id}>
                        <Link
                          href={`/incidents/${incident.id}`}
                          className="flex items-center gap-3 py-2.5 transition-colors hover:bg-surface-2/60"
                        >
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border bg-surface-2 text-muted-foreground">
                            <Icon className="h-4 w-4" aria-hidden="true" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm">
                              {ruleLabel(incident.event_type)}
                            </p>
                            <p className="text-[11px] text-muted-foreground">
                              {cameraNames.get(incident.camera_id) ??
                                `Camera #${incident.camera_id}`}
                              {" · "}
                              {timeAgo(incident.first_seen_at)}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <SeverityBadge severity={incident.severity} />
                            <StatusBadge status={incident.status} />
                          </div>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
