"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ExternalLink,
  Loader2,
  Play,
  Radio,
  Square,
  TriangleAlert,
} from "lucide-react";
import { ErrorState } from "@/components/empty-state";
import { LiveQrCard } from "@/components/live-qr-card";
import { LiveViewer } from "@/components/live/live-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, apiErrorMessage } from "@/lib/api";
import { ruleLabel, severityInfo, severityVariant } from "@/lib/labels";
import type { LiveIncidentMessage, LiveSession } from "@/types";

const SESSION_KEY = "live-session";

const steps = [
  {
    title: "Start a session",
    description:
      "The dashboard opens a live viewer and creates a short-lived, phone-only capture token.",
  },
  {
    title: "Scan the QR code",
    description:
      "Point your phone camera at the code. The capture page opens over HTTPS and asks for camera permission.",
  },
  {
    title: "Stream and detect",
    description:
      "Tap Start live stream. Frames reach this dashboard in real time and rule detections create incidents.",
  },
];

export default function LivePage() {
  const [session, setSession] = useState<LiveSession | null>(null);
  const [incidents, setIncidents] = useState<LiveIncidentMessage[]>([]);
  const [starting, setStarting] = useState(false);
  const [ending, setEnding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return;
    let saved: LiveSession;
    try {
      saved = JSON.parse(raw) as LiveSession;
    } catch {
      sessionStorage.removeItem(SESSION_KEY);
      return;
    }
    let cancelled = false;
    api
      .getLiveSession(saved.id)
      .then((status) => {
        if (cancelled || status.status === "stopped") {
          sessionStorage.removeItem(SESSION_KEY);
          return;
        }
        setSession({ ...saved, status: status.status });
      })
      .catch(() => {
        sessionStorage.removeItem(SESSION_KEY);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (session) sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }, [session]);

  const startSession = async () => {
    setStarting(true);
    setError(null);
    try {
      const created = (await api.createLiveSession()) as LiveSession;
      setSession(created);
      setIncidents([]);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not start a live session"));
    } finally {
      setStarting(false);
    }
  };

  const endSession = async () => {
    if (!session) return;
    setEnding(true);
    try {
      await api.stopLiveSession(session.id);
    } catch (err) {
      setError(apiErrorMessage(err, "Could not stop the live session"));
    } finally {
      sessionStorage.removeItem(SESSION_KEY);
      setSession(null);
      setIncidents([]);
      setEnding(false);
    }
  };

  const handleIncident = useCallback((incident: LiveIncidentMessage) => {
    setIncidents((current) => [incident, ...current].slice(0, 8));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <Radio className="h-5 w-5 text-primary" aria-hidden="true" />
            Live capture
          </h1>
          <p className="text-sm text-muted-foreground">
            Stream from a phone and watch annotated detections as they happen
          </p>
        </div>
        {session ? (
          <Button variant="destructive" onClick={endSession} disabled={ending}>
            {ending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Square className="h-4 w-4" />
            )}
            End session
          </Button>
        ) : (
          <Button onClick={startSession} disabled={starting}>
            {starting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Start live session
          </Button>
        )}
      </div>

      {error && <ErrorState message={error} />}

      {!session ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
                Connect a phone camera
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col items-start gap-3">
                <p className="max-w-2xl text-sm text-muted-foreground">
                  Start a session to create a QR code. The phone does not need
                  an account: its capture link carries a short-lived token
                  scoped to this session only.
                </p>
                <Button onClick={startSession} disabled={starting}>
                  {starting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="h-4 w-4" />
                  )}
                  Create QR code
                </Button>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {steps.map((step, index) => (
              <Card key={step.title}>
                <CardContent className="flex gap-3 p-5">
                  <span
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-xs font-semibold text-primary"
                    aria-hidden="true"
                  >
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium">{step.title}</p>
                    <p className="mt-1.5 text-sm text-muted-foreground">
                      {step.description}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(340px,1fr)]">
            <Card>
              <CardContent className="p-4">
                <LiveViewer
                  key={session.id}
                  session={session}
                  onIncident={handleIncident}
                />
              </CardContent>
            </Card>

            <div className="flex flex-col gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
                    Connect a device
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <LiveQrCard session={session} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
                    Session
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">Camera</span>
                    <span className="font-medium">{session.camera_name}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">Session ID</span>
                    <span className="font-mono text-xs">
                      {session.id.slice(0, 12)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">
                      Capture link expires
                    </span>
                    <span className="font-medium">
                      {new Date(session.expires_at).toLocaleTimeString()}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
                Live incidents
              </CardTitle>
            </CardHeader>
            <CardContent>
              {incidents.length === 0 ? (
                <div className="flex items-start gap-2 text-sm text-muted-foreground">
                  <TriangleAlert
                    className="mt-0.5 h-4 w-4 shrink-0"
                    aria-hidden="true"
                  />
                  Rule detections will appear here and are saved as incidents.
                </div>
              ) : (
                <ul className="flex flex-col gap-2">
                  {incidents.map((incident, index) => (
                    <li
                      key={`${incident.incident_id}-${incident.timestamp}-${index}`}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-surface-2 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">
                          {incident.rule_name || ruleLabel(incident.rule)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(
                            incident.timestamp * 1000,
                          ).toLocaleTimeString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={severityVariant(incident.severity)}>
                          {severityInfo(incident.severity).label}
                        </Badge>
                        {incident.incident_id !== null && (
                          <Button asChild variant="ghost" size="sm">
                            <Link href={`/incidents/${incident.incident_id}`}>
                              <ExternalLink className="h-4 w-4" />
                              View
                            </Link>
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
