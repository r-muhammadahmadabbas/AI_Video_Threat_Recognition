"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DetectionResult, RuleTrigger } from "@/types";
import { drawDetectionOverlay } from "@/lib/overlay";
import { cn } from "@/lib/utils";

interface MediaOverlayProps {
  src: string;
  mediaType: "video" | "image";
  detections: DetectionResult[];
  events: RuleTrigger[];
  className?: string;
}

interface DetectionGroup {
  timestamp: number;
  detections: DetectionResult[];
}

const MATCH_TOLERANCE_SECONDS = 0.4;

export function MediaOverlay({
  src,
  mediaType,
  detections,
  events,
  className,
}: MediaOverlayProps) {
  const mediaRef = useRef<HTMLVideoElement | HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [aspectRatio, setAspectRatio] = useState(
    mediaType === "video" ? 16 / 9 : 4 / 3,
  );

  const groups = useMemo<DetectionGroup[]>(() => {
    const byTimestamp = new Map<number, DetectionResult[]>();
    for (const detection of detections) {
      const key = Math.round(detection.timestamp * 100) / 100;
      const rows = byTimestamp.get(key);
      if (rows) rows.push(detection);
      else byTimestamp.set(key, [detection]);
    }
    return [...byTimestamp.entries()]
      .map(([timestamp, rows]) => ({ timestamp, detections: rows }))
      .sort((a, b) => a.timestamp - b.timestamp);
  }, [detections]);

  const groupAt = useCallback(
    (time: number): DetectionGroup | null => {
      if (groups.length === 0) return null;
      if (mediaType === "image") return groups[0];

      let nearest: DetectionGroup | null = null;
      let nearestDistance = Number.POSITIVE_INFINITY;
      for (const group of groups) {
        const distance = Math.abs(group.timestamp - time);
        if (distance < nearestDistance) {
          nearest = group;
          nearestDistance = distance;
        }
      }
      return nearestDistance <= MATCH_TOLERANCE_SECONDS ? nearest : null;
    },
    [groups, mediaType],
  );

  const draw = useCallback(() => {
    const media = mediaRef.current;
    const canvas = canvasRef.current;
    if (!media || !canvas) return;

    const sourceWidth =
      mediaType === "video"
        ? (media as HTMLVideoElement).videoWidth
        : (media as HTMLImageElement).naturalWidth;
    const sourceHeight =
      mediaType === "video"
        ? (media as HTMLVideoElement).videoHeight
        : (media as HTMLImageElement).naturalHeight;
    if (!sourceWidth || !sourceHeight) return;

    const rect = media.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    canvas.width = sourceWidth;
    canvas.height = sourceHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const time =
      mediaType === "video" ? (media as HTMLVideoElement).currentTime : 0;
    const group = groupAt(time);
    drawDetectionOverlay(
      ctx,
      sourceWidth,
      sourceHeight,
      rect.width,
      rect.height,
      group?.detections ?? [],
      events,
      group?.timestamp ?? time,
    );
  }, [events, groupAt, mediaType]);

  useEffect(() => {
    const media = mediaRef.current;
    if (!media) return;

    let frame = 0;
    const cancel = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
    };
    const loop = () => {
      draw();
      frame = requestAnimationFrame(loop);
    };
    const onLoaded = () => {
      const width =
        mediaType === "video"
          ? (media as HTMLVideoElement).videoWidth
          : (media as HTMLImageElement).naturalWidth;
      const height =
        mediaType === "video"
          ? (media as HTMLVideoElement).videoHeight
          : (media as HTMLImageElement).naturalHeight;
      if (width && height) setAspectRatio(width / height);
      draw();
    };
    const onPlay = () => {
      cancel();
      loop();
    };
    const onPause = () => {
      cancel();
      draw();
    };

    if (mediaType === "video") {
      const video = media as HTMLVideoElement;
      video.addEventListener("loadedmetadata", onLoaded);
      video.addEventListener("play", onPlay);
      video.addEventListener("pause", onPause);
      video.addEventListener("seeked", draw);
      video.addEventListener("timeupdate", draw);
      if (video.readyState >= 1) onLoaded();
      if (!video.paused) loop();
    } else {
      const image = media as HTMLImageElement;
      image.addEventListener("load", onLoaded);
      if (image.complete) onLoaded();
    }

    const observer = new ResizeObserver(draw);
    observer.observe(media);
    draw();

    return () => {
      cancel();
      observer.disconnect();
      if (mediaType === "video") {
        const video = media as HTMLVideoElement;
        video.removeEventListener("loadedmetadata", onLoaded);
        video.removeEventListener("play", onPlay);
        video.removeEventListener("pause", onPause);
        video.removeEventListener("seeked", draw);
        video.removeEventListener("timeupdate", draw);
      } else {
        (media as HTMLImageElement).removeEventListener("load", onLoaded);
      }
    };
  }, [draw, mediaType]);

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-border bg-black",
        className,
      )}
      style={{ aspectRatio: String(aspectRatio) }}
    >
      {mediaType === "video" ? (
        <video
          ref={mediaRef as React.RefObject<HTMLVideoElement>}
          src={src}
          controls
          playsInline
          className="absolute inset-0 h-full w-full object-contain"
        />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          ref={mediaRef as React.RefObject<HTMLImageElement>}
          src={src}
          alt="Detection result"
          className="absolute inset-0 h-full w-full object-contain"
        />
      )}
      <canvas
        ref={canvasRef}
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 h-full w-full"
      />
    </div>
  );
}
