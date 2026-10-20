"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import {
  Camera as CameraIcon,
  MapPin,
  Pencil,
  RotateCcw,
  RotateCw,
  Undo2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Camera, Paginated } from "@/types";
import { ruleLabel } from "@/lib/labels";
import { timeAgo } from "@/lib/time";
import { useFetch } from "@/hooks/use-fetch";
import { AuthenticatedImage } from "@/components/authenticated-image";
import { useShell } from "@/components/shell/shell-context";
import { SeverityBadge } from "@/components/status-badges";
import { StatusDot } from "@/components/status-dot";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCameraLayout } from "@/components/site/use-camera-layout";
import { useSitePings } from "@/components/site/use-site-pings";
import { SiteTwin } from "@/components/site/site-twin";
import { EmptyState, ErrorState } from "@/components/empty-state";

export default function SitePage() {
  const {
    data: camerasData,
    loading,
    error,
    refetch,
  } = useFetch<Paginated<Camera>>(() => api.getCameras({ page_size: 100 }), []);
  const { incidents } = useShell();

  const cameras = useMemo(() => {
    const items = camerasData?.items ?? [];
    return [...items].sort((a, b) => {
      const aOnline = a.status === "online" ? 1 : 0;
      const bOnline = b.status === "online" ? 1 : 0;
      if (aOnline !== bOnline) return aOnline - bOnline;
      return a.name.localeCompare(b.name);
    });
  }, [camerasData]);

  const cameraIds = useMemo(
    () => cameras.map((camera) => camera.id),
    [cameras],
  );
  const { layout, save, reset, hasSaved } = useCameraLayout(cameraIds);
  const pings = useSitePings(incidents);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const selected = cameras.find((camera) => camera.id === selectedId) ?? null;
  const online = selected?.status === "online";

  const selectedIncidents = useMemo(
    () =>
      incidents
        .filter((incident) => incident.camera_id === selectedId)
        .slice(0, 4),
    [incidents, selectedId],
  );

  const selectCamera = useCallback((id: number | null) => {
    setSelectedId(id);
  }, []);

  const rotate = (direction: 1 | -1) => {
    if (!selected) return;
    const placement = layout[selected.id];
    if (!placement) return;
    save(selected.id, {
      ...placement,
      yaw: placement.yaw + (direction * Math.PI) / 12,
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Site Twin</h1>
          <p className="text-sm text-muted-foreground">
            Spatial camera network with live status and threat pings
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {hasSaved ? (
            <Button
              variant="ghost"
              onClick={() => reset()}
              className="gap-1.5 text-muted-foreground"
            >
              <Undo2 className="h-4 w-4" aria-hidden="true" />
              Reset layout
            </Button>
          ) : null}
          <Button
            variant={editing ? "default" : "outline"}
            onClick={() => setEditing((value) => !value)}
            aria-pressed={editing}
            className="gap-1.5"
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
            {editing ? "Done editing" : "Edit layout"}
          </Button>
        </div>
      </div>

      {error ? <ErrorState message={error} /> : null}

      {editing ? (
        <p className="rounded-md border border-border bg-surface-2 px-3 py-2 text-xs text-muted-foreground">
          Drag cameras on the 2D map to move them.
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_minmax(0,1fr)_300px]">
        <Card className="order-2 max-h-[560px] overflow-auto lg:order-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">
              Cameras{" "}
              <span className="font-mono text-xs font-normal text-muted-foreground">
                {cameras.length}
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-2">
            {loading && cameras.length === 0 ? (
              <div className="flex flex-col gap-2 p-1">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-9" />
                ))}
              </div>
            ) : cameras.length === 0 ? (
              <EmptyState
                title="No cameras"
                description="Add a camera to populate the site map."
                icon={CameraIcon}
              />
            ) : (
              <ul id="site-camera-list" className="flex flex-col gap-0.5">
                {cameras.map((camera) => {
                  const isOnline = camera.status === "online";
                  return (
                    <li key={camera.id}>
                      <button
                        type="button"
                        onClick={() => setSelectedId(camera.id)}
                        aria-pressed={selectedId === camera.id}
                        className={`flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors ${
                          selectedId === camera.id
                            ? "bg-surface-3 text-foreground"
                            : "text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                        }`}
                      >
                        <StatusDot online={isOnline} />
                        <span className="min-w-0 flex-1 truncate">
                          {camera.name}
                        </span>
                        <span className="text-[11px]">
                          {isOnline ? "Online" : "Offline"}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            <Button
              asChild
              variant="ghost"
              size="sm"
              className="mt-2 w-full justify-start gap-1.5 text-xs text-muted-foreground"
            >
              <Link href="/cameras">
                <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
                Manage cameras
              </Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="order-1 overflow-hidden lg:order-2">
          <div className="h-[420px] w-full sm:h-[480px] lg:h-[560px]">
            <SiteTwin
              cameras={cameras}
              layout={layout}
              selectedId={selectedId}
              onSelect={selectCamera}
              incidents={incidents}
              pings={pings}
              listId="site-camera-list"
              editable={editing}
              onMove={save}
            />
          </div>
        </Card>

        <Card className="order-3">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">
              {selected ? selected.name : "Camera details"}
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {!selected ? (
              <EmptyState
                title="Select a camera"
                description="Choose a camera from the list or click a node on the map."
                icon={CameraIcon}
              />
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="inline-flex items-center gap-1.5">
                    <StatusDot online={online} />
                    {online ? "Online" : "Offline"}
                  </span>
                  <span className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">
                    {selected.source_type}
                  </span>
                  {selected.inference_enabled ? (
                    <span className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11px] text-muted-foreground">
                      Inference {selected.inference_fps ?? "—"} fps
                    </span>
                  ) : null}
                </div>

                <div className="relative aspect-video overflow-hidden rounded-md border border-border bg-surface-2">
                  <AuthenticatedImage
                    src={api.getCameraSnapshot(selected.id)}
                    alt={`Latest snapshot from ${selected.name}`}
                    className="h-full w-full object-cover"
                  />
                </div>

                {editing ? (
                  <div className="flex flex-col gap-2 rounded-md border border-border bg-surface-2 p-2">
                    <p className="text-xs text-muted-foreground">
                      Rotate the field-of-view direction
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => rotate(-1)}
                        className="flex-1 gap-1"
                      >
                        <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                        Left
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => rotate(1)}
                        className="flex-1 gap-1"
                      >
                        <RotateCw className="h-3.5 w-3.5" aria-hidden="true" />
                        Right
                      </Button>
                    </div>
                  </div>
                ) : null}

                <div className="flex flex-col gap-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Recent incidents
                  </p>
                  {selectedIncidents.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      No recent incidents for this camera.
                    </p>
                  ) : (
                    <ul className="flex flex-col gap-1">
                      {selectedIncidents.map((incident) => (
                        <li key={incident.id}>
                          <Link
                            href={`/incidents/${incident.id}`}
                            className="flex items-center justify-between gap-2 rounded px-1 py-1.5 text-xs transition-colors hover:bg-surface-2"
                          >
                            <span className="min-w-0 flex-1 truncate">
                              {ruleLabel(incident.event_type)}
                            </span>
                            <SeverityBadge severity={incident.severity} />
                            <span className="shrink-0 text-muted-foreground">
                              {timeAgo(incident.first_seen_at)}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <Button asChild variant="ghost" size="sm">
                  <Link href="/incidents">All incidents</Link>
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {!loading && !error ? (
        <p className="text-xs text-muted-foreground">
          Camera positions are not stored by the API. This layout is saved in
          this browser only, so other operators won&apos;t see it.{" "}
          <button
            type="button"
            onClick={() => refetch()}
            className="underline underline-offset-2 hover:text-foreground"
          >
            Refresh
          </button>
        </p>
      ) : null}
    </div>
  );
}
