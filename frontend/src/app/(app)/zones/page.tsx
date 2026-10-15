"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  Edit,
  Loader2,
  MapPin,
  Plus,
  RotateCcw,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiErrorMessage } from "@/lib/api";
import { Camera, Paginated, PolygonPoint, Zone } from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { useAuthenticatedBlob } from "@/hooks/use-authenticated-blob";
import { EmptyState, ErrorState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

const ZONE_TYPES = ["restricted", "loitering", "privacy", "crowd"];

function drawCanvas(
  context: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  image: HTMLImageElement | null,
  points: PolygonPoint[],
) {
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (image) {
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
  } else {
    context.fillStyle = "#0f172a";
    context.fillRect(0, 0, canvas.width, canvas.height);
  }

  if (points.length === 0) return;
  context.strokeStyle = "#22c55e";
  context.lineWidth = 2;
  context.beginPath();
  points.forEach((point, index) => {
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  });
  if (points.length > 2) {
    context.closePath();
    context.fillStyle = "rgba(34, 197, 94, 0.15)";
    context.fill();
  }
  context.stroke();

  points.forEach((point, index) => {
    context.fillStyle = index === 0 ? "#16a34a" : "#22c55e";
    context.beginPath();
    context.arc(point.x, point.y, 5, 0, Math.PI * 2);
    context.fill();
    context.strokeStyle = "white";
    context.lineWidth = 2;
    context.stroke();
  });
}

function PolygonEditor({
  cameraId,
  initialPolygon,
  onChange,
  frameWidth,
  frameHeight,
}: {
  cameraId: number;
  initialPolygon: PolygonPoint[][];
  onChange: (polygon: PolygonPoint[][]) => void;
  frameWidth: number;
  frameHeight: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const { objectUrl, loading } = useAuthenticatedBlob(
    api.getCameraSnapshot(cameraId),
  );
  const [points, setPoints] = useState<PolygonPoint[]>(initialPolygon[0] ?? []);
  const [history, setHistory] = useState<PolygonPoint[][]>([
    initialPolygon[0] ?? [],
  ]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const [loadedUrl, setLoadedUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!objectUrl) return;
    const image = new Image();
    image.onload = () => {
      imageRef.current = image;
      setLoadedUrl(objectUrl);
    };
    image.src = objectUrl;
  }, [objectUrl]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    drawCanvas(context, canvas, imageRef.current, points);
  }, [points, loadedUrl]);

  useEffect(() => {
    onChange([points]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points]);

  const pushHistory = (nextPoints: PolygonPoint[]) => {
    const next = history.slice(0, historyIndex + 1);
    next.push(nextPoints);
    setHistory(next);
    setHistoryIndex(next.length - 1);
  };

  const handleClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.round(
      ((event.clientX - rect.left) * frameWidth) / rect.width,
    );
    const y = Math.round(
      ((event.clientY - rect.top) * frameHeight) / rect.height,
    );
    const nextPoints = [
      ...points,
      {
        x: Math.max(0, Math.min(frameWidth - 1, x)),
        y: Math.max(0, Math.min(frameHeight - 1, y)),
      },
    ];
    setPoints(nextPoints);
    pushHistory(nextPoints);
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="relative overflow-hidden rounded-md border border-border">
        <canvas
          ref={canvasRef}
          width={frameWidth}
          height={frameHeight}
          onClick={handleClick}
          className="h-auto w-full cursor-crosshair"
        />
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            if (historyIndex > 0) {
              const nextIndex = historyIndex - 1;
              setHistoryIndex(nextIndex);
              setPoints(history[nextIndex]);
            }
          }}
          disabled={historyIndex <= 0}
        >
          <Undo2 className="h-4 w-4" />
          Undo
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            const nextPoints = points.slice(0, -1);
            setPoints(nextPoints);
            pushHistory(nextPoints);
          }}
          disabled={points.length === 0}
        >
          <X className="h-4 w-4" />
          Remove last
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            if (points.length < 3) return;
            const nextPoints = [...points, { ...points[0] }];
            setPoints(nextPoints);
            pushHistory(nextPoints);
          }}
          disabled={points.length < 3}
        >
          <RotateCcw className="h-4 w-4" />
          Close polygon
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => {
            setPoints([]);
            pushHistory([]);
          }}
        >
          Clear
        </Button>
        <span className="ml-auto text-xs text-muted-foreground">
          {points.length} point{points.length === 1 ? "" : "s"}
        </span>
      </div>
    </div>
  );
}

interface ZoneForm {
  name: string;
  camera_id: number;
  zone_type: string;
  polygon: PolygonPoint[][];
  is_active: boolean;
}

const emptyForm: ZoneForm = {
  name: "",
  camera_id: 0,
  zone_type: "restricted",
  polygon: [[]],
  is_active: true,
};

export default function ZonesPage() {
  const { data, loading, error, refetch } = useFetch<Paginated<Zone>>(
    () => api.getZones({ page: 1, page_size: 50 }),
    [],
  );
  const { data: camerasData } = useFetch<Paginated<Camera>>(
    () => api.getCameras({ page_size: 100 }),
    [],
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Zone | null>(null);
  const [form, setForm] = useState<ZoneForm>(emptyForm);
  const [saving, setSaving] = useState(false);

  const cameraName = (cameraId: number) =>
    camerasData?.items.find((camera) => camera.id === cameraId)?.name ??
    `Camera #${cameraId}`;

  const selectedCamera = camerasData?.items.find(
    (camera) => camera.id === form.camera_id,
  );
  const frameWidth = selectedCamera?.width || 640;
  const frameHeight = selectedCamera?.height || 480;

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (zone: Zone) => {
    setEditing(zone);
    setForm({
      name: zone.name,
      camera_id: zone.camera_id,
      zone_type: zone.zone_type,
      polygon: zone.polygon?.length ? zone.polygon : [[]],
      is_active: zone.is_active,
    });
    setOpen(true);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const points = form.polygon?.[0] ?? [];
    if (points.length < 3) {
      toast.error("Draw at least 3 points to form a polygon");
      return;
    }
    setSaving(true);
    try {
      if (editing) {
        await api.updateZone(editing.id, form);
        toast.success("Zone updated");
      } else {
        await api.createZone(form);
        toast.success("Zone created");
      }
      setOpen(false);
      refetch();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not save zone"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (zone: Zone) => {
    if (!window.confirm(`Delete zone "${zone.name}"?`)) return;
    try {
      await api.deleteZone(zone.id);
      toast.success("Zone deleted");
      refetch();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not delete zone"));
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Zones</h1>
          <p className="text-sm text-muted-foreground">
            Define detection zones on camera feeds
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add Zone
        </Button>
      </div>

      {error && <ErrorState message={error} />}

      <Card>
        <CardContent className="p-5">
          {loading && !data ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-12" />
              ))}
            </div>
          ) : !data || data.items.length === 0 ? (
            <EmptyState
              title="No zones defined"
              description="Draw polygons on a camera snapshot to activate zone rules."
              icon={MapPin}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Name</TableHeaderCell>
                  <TableHeaderCell>Camera</TableHeaderCell>
                  <TableHeaderCell>Type</TableHeaderCell>
                  <TableHeaderCell>Active</TableHeaderCell>
                  <TableHeaderCell>Points</TableHeaderCell>
                  <TableHeaderCell className="text-right">
                    Actions
                  </TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((zone) => (
                  <TableRow key={zone.id}>
                    <TableCell className="font-medium">{zone.name}</TableCell>
                    <TableCell>{cameraName(zone.camera_id)}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="capitalize">
                        {zone.zone_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={zone.is_active ? "success" : "secondary"}>
                        {zone.is_active ? "Yes" : "No"}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {zone.polygon?.[0]?.length ?? 0}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(zone)}
                        title="Edit"
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(zone)}
                        title="Delete"
                        className="text-red-500 hover:text-red-600"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Zone" : "Add Zone"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="zone-name">Name</Label>
                <Input
                  id="zone-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label>Camera</Label>
                <Select
                  value={String(form.camera_id || "")}
                  onValueChange={(value) =>
                    setForm({ ...form, camera_id: Number(value) })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select camera" />
                  </SelectTrigger>
                  <SelectContent>
                    {camerasData?.items.map((camera) => (
                      <SelectItem key={camera.id} value={String(camera.id)}>
                        {camera.name}
                        {camera.width && camera.height
                          ? ` (${camera.width}×${camera.height})`
                          : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <Label>Zone type</Label>
              <Select
                value={form.zone_type}
                onValueChange={(value) =>
                  setForm({ ...form, zone_type: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ZONE_TYPES.map((type) => (
                    <SelectItem key={type} value={type} className="capitalize">
                      {type}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-2">
              <Label>Polygon editor</Label>
              <p className="text-xs text-muted-foreground">
                Click the snapshot to add points, then close the polygon.
              </p>
              {form.camera_id ? (
                <PolygonEditor
                  cameraId={form.camera_id}
                  initialPolygon={form.polygon}
                  onChange={(polygon) =>
                    setForm((prev) => ({ ...prev, polygon }))
                  }
                  frameWidth={frameWidth}
                  frameHeight={frameHeight}
                />
              ) : (
                <div className="rounded-md border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                  Select a camera to load its snapshot and draw the polygon
                </div>
              )}
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) =>
                  setForm({ ...form, is_active: e.target.checked })
                }
              />
              Active
            </label>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
