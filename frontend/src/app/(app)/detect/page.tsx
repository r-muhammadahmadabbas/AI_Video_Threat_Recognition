"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  FileImage,
  FileVideo,
  Loader2,
  Radio,
  ScanSearch,
  UploadCloud,
  X,
} from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { DetectionResponse } from "@/types";
import { cn } from "@/lib/utils";
import { AnalysisReport } from "@/components/detection/AnalysisReport";
import { LiveQrCard } from "@/components/live-qr-card";
import { ErrorState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Tab = "video" | "image" | "live";

function useObjectUrl(file: File | null) {
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);
  return url;
}

function UploadPanel({ kind }: { kind: "video" | "image" }) {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<DetectionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const previewUrl = useObjectUrl(file);

  const isVideo = kind === "video";
  const accept = isVideo ? ".mp4,.avi,.mov,.webm" : ".jpg,.jpeg,.png,.webp";

  const handleSelect = (selected: File | null) => {
    setFile(selected);
    setResult(null);
    setError(null);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) handleSelect(dropped);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response: DetectionResponse = isVideo
        ? await api.detectVideo(file)
        : await api.detectImage(file);
      setResult(response);
    } catch (err) {
      setError(apiErrorMessage(err, "Analysis failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
          dragging
            ? "border-primary bg-primary/10"
            : "border-border-strong bg-surface-2/40 hover:border-primary/50 hover:bg-surface-3/40",
        )}
      >
        <UploadCloud
          className={cn(
            "h-8 w-8",
            dragging ? "text-primary" : "text-muted-foreground",
          )}
          aria-hidden="true"
        />
        <span className="text-sm font-medium">
          {file
            ? file.name
            : `Drop a ${isVideo ? "video" : "image"} here or click to browse`}
        </span>
        <span className="text-xs text-muted-foreground">
          {isVideo
            ? "MP4, AVI, MOV or WEBM · max 500MB"
            : "JPG, PNG or WEBP · analyzed instantly"}
        </span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(event) => handleSelect(event.target.files?.[0] ?? null)}
      />

      {file && (
        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-2 px-3 py-2">
          <span className="min-w-0 flex-1 truncate text-sm">{file.name}</span>
          <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
            {(file.size / 1024 / 1024).toFixed(1)} MB
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={() => handleSelect(null)}
            aria-label="Remove selected file"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
        </div>
      )}

      {file && previewUrl && (
        <div className="relative overflow-hidden rounded-xl border border-border bg-black">
          {loading && (
            <div
              className="pointer-events-none absolute inset-0 z-10 overflow-hidden"
              aria-hidden="true"
            >
              <div className="scan-line h-16 w-full bg-gradient-to-b from-transparent via-primary/30 to-transparent">
                <div className="absolute inset-x-0 top-1/2 h-px bg-primary shadow-[0_0_18px_2px_var(--primary)]" />
              </div>
            </div>
          )}
          {isVideo ? (
            <video src={previewUrl} controls className="max-h-[420px] w-full" />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={previewUrl}
              alt="Upload preview"
              className="max-h-[420px] w-full object-contain"
            />
          )}
        </div>
      )}

      <Button
        onClick={handleAnalyze}
        disabled={!file || loading}
        className="w-full gap-2 sm:w-auto"
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Analyzing — this can take a moment
          </>
        ) : (
          <>
            <ScanSearch className="h-4 w-4" aria-hidden="true" />
            Run threat analysis
          </>
        )}
      </Button>

      {error && <ErrorState message={error} />}

      {result && (
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Analysis report
          </h2>
          <AnalysisReport result={result} />
        </div>
      )}
    </div>
  );
}

const TAB_HEADERS: Record<Tab, { title: string; description: string }> = {
  video: {
    title: "Upload a recorded video",
    description:
      "The model scans sampled frames, applies every detection rule, and produces a categorized report with annotated evidence frames.",
  },
  image: {
    title: "Upload a photo or frame",
    description:
      "Single images are analyzed immediately: every weapon, person and anomaly is identified with a confidence score.",
  },
  live: {
    title: "Stream live from your phone",
    description:
      "Scan the QR code with a phone and record the scene live. The clip is analyzed the moment you stop.",
  },
};

export default function DetectPage() {
  const [tab, setTab] = useState<Tab>("video");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          Threat detection
        </h1>
        <p className="text-sm text-muted-foreground">
          Upload footage or stream live from a mobile device for instant
          analysis
        </p>
      </div>

      <Tabs value={tab} onValueChange={(value) => setTab(value as Tab)}>
        <TabsList className="w-full max-w-xl">
          <TabsTrigger value="video" className="flex-1 gap-2">
            <FileVideo className="h-4 w-4" aria-hidden="true" />
            Video upload
          </TabsTrigger>
          <TabsTrigger value="image" className="flex-1 gap-2">
            <FileImage className="h-4 w-4" aria-hidden="true" />
            Image upload
          </TabsTrigger>
          <TabsTrigger value="live" className="flex-1 gap-2">
            <Radio className="h-4 w-4" aria-hidden="true" />
            Live stream
          </TabsTrigger>
        </TabsList>

        <TabsContent value="video">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {TAB_HEADERS.video.title}
              </CardTitle>
              <CardDescription>{TAB_HEADERS.video.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <UploadPanel kind="video" />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="image">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {TAB_HEADERS.image.title}
              </CardTitle>
              <CardDescription>{TAB_HEADERS.image.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <UploadPanel kind="image" />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="live">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {TAB_HEADERS.live.title}
              </CardTitle>
              <CardDescription>{TAB_HEADERS.live.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <LiveQrCard />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
