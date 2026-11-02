"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Circle, Loader2, Radio, Square, Video } from "lucide-react";
import { ErrorState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { API_BASE } from "@/lib/api";

const FRAME_INTERVAL_MS = 100;
const MAX_FRAME_WIDTH = 960;
const MAX_BUFFERED_BYTES = 1_500_000;

function ingestUrl(sessionId: string, token: string, apiBase: string) {
  const base = (apiBase || API_BASE).replace(/^http/, "ws").replace(/\/$/, "");
  return `${base}/live/sessions/${encodeURIComponent(sessionId)}/ingest?token=${encodeURIComponent(token)}`;
}

function CaptureScreen() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session");
  const token = searchParams.get("token");
  const apiBase = searchParams.get("api") || API_BASE;

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sendingRef = useRef(false);
  const stoppingRef = useRef(false);
  const retriesRef = useRef(0);
  const startStreamRef = useRef<(() => Promise<void>) | null>(null);

  const [phase, setPhase] = useState<
    "idle" | "connecting" | "live" | "stopped"
  >("idle");
  const [error, setError] = useState<string | null>(null);
  const [frames, setFrames] = useState(0);

  const clearCaptureTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const stopStream = useCallback(
    (notifyServer: boolean) => {
      stoppingRef.current = true;
      clearCaptureTimer();
      stopCamera();
      const socket = socketRef.current;
      socketRef.current = null;
      if (socket) {
        if (socket.readyState === WebSocket.OPEN && notifyServer) {
          socket.send(JSON.stringify({ type: "stop" }));
        }
        socket.close();
      }
      setPhase("stopped");
    },
    [clearCaptureTimer, stopCamera],
  );

  const startFrameLoop = useCallback(() => {
    clearCaptureTimer();
    intervalRef.current = setInterval(() => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const socket = socketRef.current;
      if (
        !video ||
        !canvas ||
        !socket ||
        socket.readyState !== WebSocket.OPEN ||
        sendingRef.current ||
        socket.bufferedAmount > MAX_BUFFERED_BYTES
      ) {
        return;
      }

      const sourceWidth = video.videoWidth;
      const sourceHeight = video.videoHeight;
      if (!sourceWidth || !sourceHeight) return;

      const scale = Math.min(1, MAX_FRAME_WIDTH / sourceWidth);
      const width = Math.round(sourceWidth * scale);
      const height = Math.round(sourceHeight * scale);
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }

      const context = canvas.getContext("2d");
      if (!context) return;
      context.drawImage(video, 0, 0, width, height);

      sendingRef.current = true;
      canvas.toBlob(
        (blob) => {
          sendingRef.current = false;
          if (!blob || !socketRef.current) return;
          if (socketRef.current.readyState !== WebSocket.OPEN) return;
          socketRef.current.send(blob);
          setFrames((count) => count + 1);
        },
        "image/jpeg",
        0.7,
      );
    }, FRAME_INTERVAL_MS);
  }, [clearCaptureTimer]);

  const startStream = useCallback(async () => {
    if (!sessionId || !token) return;
    setError(null);
    setFrames(0);
    setPhase("connecting");
    stoppingRef.current = false;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
    } catch (err) {
      setPhase("idle");
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Camera permission was denied. Allow camera access in your browser settings."
          : "Could not access the camera. HTTPS is required on mobile browsers.",
      );
      return;
    }

    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      try {
        await videoRef.current.play();
      } catch {
        // Muted inline playback can still start on the next user interaction.
      }
    }

    const socket = new WebSocket(ingestUrl(sessionId, token, apiBase));
    socket.binaryType = "arraybuffer";
    socketRef.current = socket;

    socket.onopen = () => {
      if (stoppingRef.current) return;
      retriesRef.current = 0;
      setPhase("live");
      startFrameLoop();
    };

    socket.onerror = () => {
      if (stoppingRef.current) return;
      clearCaptureTimer();
      stopCamera();
      setPhase("stopped");
      setError(
        "Could not reach the live server. Check the API URL and try again.",
      );
    };

    socket.onclose = () => {
      if (stoppingRef.current) return;
      clearCaptureTimer();
      stopCamera();
      if (retriesRef.current >= 5) {
        setPhase("stopped");
        setError(
          "The live connection closed. Open this page again from the same QR code and tap Start.",
        );
        return;
      }
      retriesRef.current += 1;
      setPhase("connecting");
      setError(null);
      window.setTimeout(() => {
        if (!stoppingRef.current) void startStreamRef.current?.();
      }, 800);
    };
  }, [
    apiBase,
    clearCaptureTimer,
    sessionId,
    startFrameLoop,
    stopCamera,
    token,
  ]);

  useEffect(() => {
    startStreamRef.current = startStream;
  }, [startStream]);

  useEffect(() => {
    return () => {
      stoppingRef.current = true;
      clearCaptureTimer();
      stopCamera();
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, [clearCaptureTimer, stopCamera]);

  useEffect(() => {
    const onBeforeUnload = () => {
      stoppingRef.current = true;
      socketRef.current?.close();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  const mm = String(Math.floor(frames / 10 / 60)).padStart(2, "0");
  const ss = String(Math.floor(frames / 10) % 60).padStart(2, "0");

  if (!sessionId || !token) {
    return (
      <div className="mx-auto flex min-h-screen w-full max-w-lg flex-col justify-center gap-4 p-6">
        <ErrorState message="This capture link is incomplete. Scan the QR code from the live dashboard again." />
      </div>
    );
  }

  const live = phase === "live";
  const connecting = phase === "connecting";

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-semibold">
          <Radio className="h-4 w-4 text-primary" />
          Live capture
        </span>
        <Badge
          variant={live ? "success" : connecting ? "warning" : "secondary"}
        >
          {live ? "Streaming" : connecting ? "Connecting" : "Camera off"}
        </Badge>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="relative aspect-[3/4] overflow-hidden rounded-lg bg-black sm:aspect-video">
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="h-full w-full object-cover"
            />
            <canvas ref={canvasRef} className="hidden" />
            {phase === "idle" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center text-white/80">
                <Video className="h-10 w-10" />
                <p className="text-sm">
                  Your camera stays on this phone. Only compressed frames are
                  sent to the dashboard.
                </p>
                <Button onClick={startStream}>Start live stream</Button>
              </div>
            )}
            {connecting && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-white/80">
                <Loader2 className="h-6 w-6 animate-spin" />
                <p className="text-sm">
                  Starting camera and live connection...
                </p>
              </div>
            )}
            {live && (
              <div className="absolute left-3 top-3 flex items-center gap-2 rounded-full bg-sev-critical-solid px-3 py-1 text-xs font-semibold text-white">
                <Circle
                  className="h-3 w-3 animate-pulse fill-current"
                  aria-hidden="true"
                />
                LIVE {mm}:{ss}
              </div>
            )}
          </div>

          <div className="mt-4 flex items-center justify-center gap-3">
            {live && (
              <Button variant="destructive" onClick={() => stopStream(true)}>
                <Square className="h-4 w-4" />
                Stop stream
              </Button>
            )}
            {phase === "stopped" && (
              <Button onClick={startStream}>Start again</Button>
            )}
          </div>

          {live && (
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Streaming {frames} frames. Detections are drawn on the dashboard,
              not on this phone.
            </p>
          )}
          {phase === "stopped" && !error && (
            <p className="mt-3 text-center text-xs text-muted-foreground">
              The stream is stopped. Return to the dashboard to start a new
              session.
            </p>
          )}
          {error && <ErrorState className="mt-3" message={error} />}
        </CardContent>
      </Card>
    </div>
  );
}

export default function LiveCapturePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <CaptureScreen />
    </Suspense>
  );
}
