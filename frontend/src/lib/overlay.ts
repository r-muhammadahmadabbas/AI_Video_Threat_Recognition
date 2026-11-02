import type { DetectionResult, RuleTrigger } from "@/types";
import { classInfo, ruleLabel } from "@/lib/labels";

const EVENT_COLORS: Record<string, string> = {
  critical: "#dc2626",
  high: "#f97316",
  medium: "#eab308",
  low: "#38bdf8",
};

function eventForDetection(
  detection: DetectionResult,
  events: RuleTrigger[],
  timestamp: number,
): RuleTrigger | null {
  return (
    events.find(
      (event) =>
        Math.abs(event.timestamp - timestamp) <= 0.12 &&
        event.tracker_ids.includes(detection.track_id),
    ) ?? null
  );
}

/**
 * Draw boxes and labels onto a canvas that has the source frame's intrinsic
 * dimensions. Bounding boxes stay in source pixels; the canvas is scaled by CSS.
 */
export function drawDetectionOverlay(
  ctx: CanvasRenderingContext2D,
  sourceWidth: number,
  sourceHeight: number,
  displayWidth: number,
  displayHeight: number,
  detections: DetectionResult[],
  events: RuleTrigger[],
  timestamp: number,
): void {
  ctx.clearRect(0, 0, sourceWidth, sourceHeight);
  if (sourceWidth <= 0 || sourceHeight <= 0 || displayWidth <= 0) return;

  const scale = Math.max(
    1,
    Math.min(sourceWidth / displayWidth, sourceHeight / displayHeight),
  );
  const lineWidth = Math.max(1, 2 * scale);
  const fontSize = Math.max(11, 12 * scale);
  const padding = 4 * scale;

  ctx.lineWidth = lineWidth;
  ctx.font = `600 ${fontSize}px ui-sans-serif, system-ui, sans-serif`;
  ctx.textBaseline = "middle";

  for (const detection of detections) {
    if (detection.bbox.length < 4) continue;
    const [x1, y1, x2, y2] = detection.bbox;
    const event = eventForDetection(detection, events, timestamp);

    const color = event
      ? (EVENT_COLORS[event.severity] ?? "#f97316")
      : detection.is_threat || detection.weapon
        ? "#ef4444"
        : "#22d3ee";

    const label = event
      ? ruleLabel(event.rule)
      : `${classInfo(detection.class_name).short} ${(detection.confidence * 100).toFixed(0)}%`;

    ctx.strokeStyle = color;
    ctx.strokeRect(x1, y1, Math.max(1, x2 - x1), Math.max(1, y2 - y1));

    const textWidth = ctx.measureText(label).width;
    const boxHeight = fontSize + padding * 2;
    const above = y1 - boxHeight - padding >= 0;
    const labelY = above ? y1 - boxHeight - padding : y2 + padding;

    ctx.fillStyle = "rgba(0, 0, 0, 0.78)";
    ctx.fillRect(x1, labelY, textWidth + padding * 2, boxHeight);
    ctx.fillStyle = color;
    ctx.fillText(label, x1 + padding, labelY + boxHeight / 2);
  }
}
