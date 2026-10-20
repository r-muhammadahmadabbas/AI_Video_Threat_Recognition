"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Circle, Loader2, Radio, Square, Video } from "lucide-react";
import { AuthGuard } from "@/components/auth-guard";
import { AnalysisReport } from "@/components/detection/AnalysisReport";
import { ErrorState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, apiErrorMessage } from "@/lib/api";
import { DetectionResponse } from "@/types";

function CaptureScreen() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const [cameraOn, setCameraOn] = useState(false);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DetectionResponse | null>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraOn(false);
    setRecording(false);
  }, []);

  const startCamera = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraOn(true);
    } catch (err) {
      setError(
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Camera permission was denied. Allow camera access in your browser settings."
          : "Could not access the camera. HTTPS (or localhost) is required on mobile browsers.",
      );
    }
  }, []);

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  useEffect(() => {
    if (!recording) return;
    const interval = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [recording]);

  const uploadClip = useCallback(async (blob: Blob, mimeType: string) => {
    setUploading(true);
    setError(null);
    try {
      const extension = mimeType.includes("mp4") ? "mp4" : "webm";
      const file = new File([blob], `live-capture.${extension}`, {
        type: mimeType,
      });
      const response: DetectionResponse = await api.detectVideo(file);
      setResult(response);
    } catch (err) {
      setError(apiErrorMessage(err, "Analysis failed"));
    } finally {
      setUploading(false);
    }
  }, []);

  const startRecording = useCallback(() => {
    if (!streamRef.current) return;
    setResult(null);
    setError(null);
    setSeconds(0);
    chunksRef.current = [];

    const mimeType = ["video/mp4", "video/webm;codecs=h264", "video/webm"].find(
      (type) => MediaRecorder.isTypeSupported(type),
    );

    const recorder = new MediaRecorder(
      streamRef.current,
      mimeType ? { mimeType } : undefined,
    );
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const type = recorder.mimeType || "video/webm";
      const blob = new Blob(chunksRef.current, { type });
      if (blob.size > 0) uploadClip(blob, type);
    };
    recorderRef.current = recorder;
    recorder.start(1000);
    setRecording(true);
  }, [uploadClip]);

  const stopRecording = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  }, []);

  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <Button asChild variant="ghost" size="sm">
          <Link href="/">
            <ArrowLeft className="h-4 w-4" />
            Dashboard
          </Link>
        </Button>
        <span className="flex items-center gap-2 text-sm font-semibold">
          <Radio className="h-4 w-4 text-primary" />
          Live Capture
        </span>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="relative overflow-hidden rounded-lg bg-black aspect-[3/4] sm:aspect-video">
            <video
              ref={videoRef}
              autoPlay
              muted
              playsInline
              className="h-full w-full object-cover"
            />
            {!cameraOn && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-white/80">
                <Video className="h-10 w-10" />
                <p className="text-sm">Camera is off</p>
                <Button onClick={startCamera}>Start Camera</Button>
              </div>
            )}
            {recording && (
              <div className="absolute left-3 top-3 flex items-center gap-2 rounded-full bg-sev-critical-solid px-3 py-1 text-xs font-semibold text-white">
                <Circle
                  className="h-3 w-3 animate-pulse fill-current"
                  aria-hidden="true"
                />
                REC {mm}:{ss}
              </div>
            )}
          </div>

          <div className="mt-4 flex items-center justify-center gap-3">
            {cameraOn && !recording && (
              <Button onClick={startRecording} disabled={uploading}>
                <Circle
                  className="h-4 w-4 fill-current text-sev-critical"
                  aria-hidden="true"
                />
                Start Recording
              </Button>
            )}
            {recording && (
              <Button variant="destructive" onClick={stopRecording}>
                <Square className="h-4 w-4" />
                Stop &amp; Analyze
              </Button>
            )}
            {cameraOn && !recording && (
              <Button
                variant="outline"
                onClick={stopCamera}
                disabled={uploading}
              >
                Turn Off Camera
              </Button>
            )}
          </div>

          {cameraOn && !recording && !uploading && (
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Record the scene, then stop to run threat analysis instantly.
            </p>
          )}
          {uploading && (
            <div className="mt-3 flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing footage, this can take a moment...
            </div>
          )}
          {error && <ErrorState className="mt-3" message={error} />}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Analysis Report</CardTitle>
          </CardHeader>
          <CardContent>
            <AnalysisReport result={result} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function LiveCapturePage() {
  return (
    <AuthGuard>
      <CaptureScreen />
    </AuthGuard>
  );
}
