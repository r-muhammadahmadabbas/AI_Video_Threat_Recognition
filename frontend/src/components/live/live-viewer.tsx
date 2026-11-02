"use client";

import { useEffect, useRef, useState } from "react";
import { Radio, TriangleAlert, Wifi, WifiOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { websocketUrl } from "@/lib/api";
import { drawDetectionOverlay } from "@/lib/overlay";
import type {
  LiveIncidentMessage,
  LiveMetadata,
  LiveSession,
  LiveStatusMessage,
} from "@/types";

interface LiveViewerProps {
  session: LiveSession;
  onIncident?: (incident: LiveIncidentMessage) => void;
}

export function LiveViewer({ session, onIncident }: LiveViewerProps) {
  const frameCanvasRef = useRef<HTMLCanvasElement>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement>(null);
  const metadataRef = useRef<LiveMetadata | null>(null);
  const onIncidentRef = useRef(onIncident);
  const [status, setStatus] = useState(session.status);
  const [connected, setConnected] = useState(false);
  const [hasFrame, setHasFrame] = useState(false);
  const [tracked, setTracked] = useState(0);
  const [activeDown, setActiveDown] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onIncidentRef.current = onIncident;
  }, [onIncident]);

  useEffect(() => {
    const token =
      typeof window !== "undefined"
        ? (localStorage.getItem("access_token") ?? "")
        : "";
    let disposed = false;
    let sequence = 0;

    const ws = new WebSocket(
      websocketUrl(`/live/sessions/${session.id}/watch`, { token }),
    );
    ws.binaryType = "arraybuffer";

    const drawFrame = async (buffer: ArrayBuffer) => {
      const current = ++sequence;
      let bitmap: ImageBitmap;
      try {
        bitmap = await createImageBitmap(
          new Blob([buffer], { type: "image/jpeg" }),
        );
      } catch {
        return;
      }

      if (disposed || current !== sequence) {
        bitmap.close();
        return;
      }

      const canvas = frameCanvasRef.current;
      const overlay = overlayCanvasRef.current;
      const context = canvas?.getContext("2d");
      if (!canvas || !overlay || !context) {
        bitmap.close();
        return;
      }

      if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        overlay.width = bitmap.width;
        overlay.height = bitmap.height;
      }

      context.drawImage(bitmap, 0, 0);
      paintOverlay();
      bitmap.close();
      setHasFrame(true);
    };

    const paintOverlay = () => {
      const overlay = overlayCanvasRef.current;
      const metadata = metadataRef.current;
      const overlayContext = overlay?.getContext("2d");
      if (!overlay || !overlayContext || overlay.width <= 0) return;
      if (!metadata) {
        overlayContext.clearRect(0, 0, overlay.width, overlay.height);
        return;
      }
      drawDetectionOverlay(
        overlayContext,
        overlay.width,
        overlay.height,
        overlay.clientWidth,
        overlay.clientHeight,
        metadata.detections,
        metadata.events,
        metadata.timestamp,
      );
    };

    ws.onopen = () => {
      if (!disposed) setConnected(true);
    };

    ws.onmessage = (event) => {
      if (disposed) return;
      if (typeof event.data === "string") {
        try {
          const message = JSON.parse(event.data) as
            LiveMetadata | LiveStatusMessage | LiveIncidentMessage;
          if (message.type === "status") {
            setStatus(message.status);
            if (message.status === "stopped") setActiveDown(false);
          } else if (message.type === "metadata") {
            metadataRef.current = message;
            paintOverlay();
            setTracked(message.detections.length);
            setActiveDown(
              message.events.some((event) => event.rule === "person_down"),
            );
          } else if (message.type === "incident") {
            onIncidentRef.current?.(message);
          }
        } catch {
          // Ignore malformed control messages.
        }
        return;
      }
      if (event.data instanceof ArrayBuffer) {
        void drawFrame(event.data);
      }
    };

    ws.onerror = () => {
      if (!disposed) setError("Live stream connection failed.");
    };

    ws.onclose = (event) => {
      if (disposed) return;
      setConnected(false);
      if (event.code === 4401) {
        setError("Your session expired. Sign in again.");
      } else if (event.code === 4404) {
        setError("This live session is no longer available.");
      }
    };

    return () => {
      disposed = true;
      ws.close();
    };
  }, [session.id]);

  const live = status === "live";
  const statusLabel =
    status === "stopped"
      ? "Ended"
      : !connected
        ? "Connecting"
        : live
          ? "Live"
          : "Waiting for phone";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Radio
            className={
              live ? "h-4 w-4 text-primary" : "h-4 w-4 text-muted-foreground"
            }
            aria-hidden="true"
          />
          {session.camera_name}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={live ? "success" : "secondary"}>
            {connected ? (
              <Wifi className="h-3 w-3" aria-hidden="true" />
            ) : (
              <WifiOff className="h-3 w-3" aria-hidden="true" />
            )}
            {statusLabel}
          </Badge>
          {tracked > 0 && (
            <span className="text-xs text-muted-foreground">
              {tracked} tracked
            </span>
          )}
        </div>
      </div>

      {activeDown && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-lg border border-sev-high/40 bg-sev-high-bg px-3 py-2 text-sm font-medium text-sev-high"
        >
          <TriangleAlert className="h-4 w-4" aria-hidden="true" />
          Person down — subject has not recovered
        </div>
      )}

      <div className="relative aspect-video overflow-hidden rounded-lg bg-black">
        <canvas
          ref={frameCanvasRef}
          className="absolute inset-0 h-full w-full object-contain"
        />
        <canvas
          ref={overlayCanvasRef}
          className="pointer-events-none absolute inset-0 h-full w-full object-contain"
        />
        {!hasFrame && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center text-sm text-white/70">
            <Wifi className="h-8 w-8" aria-hidden="true" />
            <p>Waiting for the phone stream</p>
            <p className="text-xs text-white/50">
              Scan the QR code and tap Start live stream.
            </p>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-sev-critical">{error}</p>}
    </div>
  );
}
