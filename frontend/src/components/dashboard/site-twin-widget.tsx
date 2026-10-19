"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import type { Camera } from "@/types";
import type { FeedIncident } from "@/components/shell/shell-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCameraLayout } from "@/components/site/use-camera-layout";
import { useSitePings } from "@/components/site/use-site-pings";
import { SiteTwin } from "@/components/site/site-twin";

export function SiteTwinWidget({
  cameras,
  incidents,
}: {
  cameras: Camera[];
  incidents: FeedIncident[];
}) {
  const cameraIds = useMemo(
    () => cameras.map((camera) => camera.id),
    [cameras],
  );
  const { layout } = useCameraLayout(cameraIds);
  const pings = useSitePings(incidents);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const selectCamera = useCallback((id: number | null) => {
    setSelectedId(id);
  }, []);

  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-3">
        <CardTitle className="text-base">Site Twin</CardTitle>
        <Link
          href="/site"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          Open Site Twin
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </CardHeader>
      <CardContent className="flex-1 p-0">
        <div className="relative aspect-[4/3] w-full border-t border-border">
          <SiteTwin
            cameras={cameras}
            layout={layout}
            selectedId={selectedId}
            onSelect={selectCamera}
            incidents={incidents}
            pings={pings}
            listId="dashboard-site-camera-list"
          />
        </div>
        <ul id="dashboard-site-camera-list" className="sr-only">
          {cameras.map((camera) => (
            <li key={camera.id}>
              {camera.name}: {camera.status}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
