"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  FileImage,
  FileVideo,
  Loader2,
  Radio,
  ScanSearch,
  UploadCloud,
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

type Tab = "video" | "image" | "live";

const tabs: {
  id: Tab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  { id: "video", label: "Video Upload", icon: FileVideo },
  { id: "image", label: "Image Upload", icon: FileImage },
  { id: "live", label: "Live Stream", icon: Radio },
];

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
  const inputRef = useRef<HTMLInputElement>(null);
  const previewUrl = useObjectUrl(file);

  const isVideo = kind === "video";
  const accept = isVideo ? ".mp4,.avi,.mov,.webm" : ".jpg,.jpeg,.png,.webp";

  const handleSelect = (selected: File | null) => {
    setFile(selected);
    setResult(null);
    setError(null);
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
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border bg-card px-6 py-10 text-center transition-colors hover:border-primary/50 hover:bg-accent/40"
        >
          <UploadCloud className="h-8 w-8 text-muted-foreground" />
          <span className="text-sm font-medium">
            {file ? file.name : `Choose a ${isVideo ? "video" : "image"} file`}
          </span>
          <span className="text-xs text-muted-foreground">
            {isVideo ? "MP4, AVI, MOV or WEBM · max 500MB" : "JPG, PNG or WEBP"}
          </span>
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(event) => handleSelect(event.target.files?.[0] ?? null)}
        />

        {file && previewUrl && (
          <div className="overflow-hidden rounded-xl border border-border bg-black">
            {isVideo ? (
              <video
                src={previewUrl}
                controls
                className="max-h-[420px] w-full"
              />
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
          className="w-full sm:w-auto"
        >
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Analyzing... this can take a moment
            </>
          ) : (
            <>
              <ScanSearch className="h-4 w-4" />
              Run Threat Analysis
            </>
          )}
        </Button>
      </div>

      {error && <ErrorState message={error} />}

      {result && (
        <div className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">Analysis Report</h2>
          <AnalysisReport result={result} />
        </div>
      )}
    </div>
  );
}

export default function DetectPage() {
  const [tab, setTab] = useState<Tab>("video");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Threat Detection</h1>
        <p className="text-sm text-muted-foreground">
          Upload footage or stream live from a mobile device for instant
          analysis
        </p>
      </div>

      <div className="flex w-full max-w-xl rounded-lg border border-border bg-card p-1">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              tab === item.id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {tab === "video" && "Upload a recorded video"}
            {tab === "image" && "Upload a photo or frame"}
            {tab === "live" && "Stream live from your phone"}
          </CardTitle>
          <CardDescription>
            {tab === "video" &&
              "The model scans sampled frames, applies every detection rule, and produces a categorized report with annotated evidence frames."}
            {tab === "image" &&
              "Single images are analyzed immediately: every weapon, person and anomaly is identified with a confidence score."}
            {tab === "live" &&
              "Scan the QR code with a phone and record the scene live. The clip is analyzed the moment you stop."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {tab === "live" ? <LiveQrCard /> : <UploadPanel kind={tab} />}
        </CardContent>
      </Card>
    </div>
  );
}
