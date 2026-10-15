"use client";

import { useState } from "react";
import {
  Edit,
  Loader2,
  Plus,
  Trash2,
  Video,
  Wifi,
  WifiOff,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiErrorMessage } from "@/lib/api";
import { Camera, Paginated } from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { EmptyState, ErrorState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

const SOURCE_TYPES = ["rtsp", "file", "webcam", "onvif"];

interface CameraForm {
  name: string;
  source_type: string;
  source_url: string;
  username: string;
  password: string;
  inference_enabled: boolean;
  inference_fps: number;
}

const emptyForm: CameraForm = {
  name: "",
  source_type: "rtsp",
  source_url: "",
  username: "",
  password: "",
  inference_enabled: true,
  inference_fps: 5,
};

export default function CamerasPage() {
  const { data, loading, error, refetch } = useFetch<Paginated<Camera>>(
    () => api.getCameras({ page: 1, page_size: 50 }),
    [],
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Camera | null>(null);
  const [form, setForm] = useState<CameraForm>(emptyForm);
  const [saving, setSaving] = useState(false);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setOpen(true);
  };

  const openEdit = (camera: Camera) => {
    setEditing(camera);
    setForm({
      name: camera.name,
      source_type: camera.source_type,
      source_url: camera.source_url,
      username: camera.username || "",
      password: "",
      inference_enabled: camera.inference_enabled ?? true,
      inference_fps: camera.inference_fps ?? 5,
    });
    setOpen(true);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const payload: Record<string, unknown> = { ...form };
      if (editing && !form.password) delete payload.password;
      if (editing) {
        await api.updateCamera(editing.id, payload);
        toast.success("Camera updated");
      } else {
        await api.createCamera(payload);
        toast.success("Camera created");
      }
      setOpen(false);
      refetch();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not save camera"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (camera: Camera) => {
    if (!window.confirm(`Delete camera "${camera.name}"?`)) return;
    try {
      await api.deleteCamera(camera.id);
      toast.success("Camera deleted");
      refetch();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not delete camera"));
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Cameras</h1>
          <p className="text-sm text-muted-foreground">
            Manage video sources and inference settings
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add Camera
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
              title="No cameras configured"
              description="Add your first camera to start zone and rule based monitoring."
              icon={Video}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Name</TableHeaderCell>
                  <TableHeaderCell>Type</TableHeaderCell>
                  <TableHeaderCell>Source</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Inference</TableHeaderCell>
                  <TableHeaderCell>FPS</TableHeaderCell>
                  <TableHeaderCell className="text-right">
                    Actions
                  </TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((camera) => {
                  const online = camera.status === "online";
                  return (
                    <TableRow key={camera.id}>
                      <TableCell className="font-medium">
                        {camera.name}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {camera.source_type?.toUpperCase()}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[220px] truncate font-mono text-xs text-muted-foreground">
                        {camera.source_url}
                      </TableCell>
                      <TableCell>
                        <span className="inline-flex items-center gap-2 text-sm">
                          {online ? (
                            <Wifi className="h-4 w-4 text-green-500" />
                          ) : (
                            <WifiOff className="h-4 w-4 text-red-500" />
                          )}
                          {camera.status || "unknown"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            camera.inference_enabled ? "success" : "secondary"
                          }
                        >
                          {camera.inference_enabled ? "On" : "Off"}
                        </Badge>
                      </TableCell>
                      <TableCell>{camera.inference_fps ?? "—"}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEdit(camera)}
                          title="Edit"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDelete(camera)}
                          title="Delete"
                          className="text-red-500 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Camera" : "Add Camera"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="camera-name">Name</Label>
              <Input
                id="camera-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Source type</Label>
              <Select
                value={form.source_type}
                onValueChange={(value) =>
                  setForm({ ...form, source_type: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SOURCE_TYPES.map((type) => (
                    <SelectItem key={type} value={type}>
                      {type.toUpperCase()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="camera-url">Source URL</Label>
              <Input
                id="camera-url"
                value={form.source_url}
                onChange={(e) =>
                  setForm({ ...form, source_url: e.target.value })
                }
                placeholder="rtsp://..."
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="camera-user">Username (optional)</Label>
                <Input
                  id="camera-user"
                  value={form.username}
                  onChange={(e) =>
                    setForm({ ...form, username: e.target.value })
                  }
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="camera-pass">Password (optional)</Label>
                <Input
                  id="camera-pass"
                  type="password"
                  value={form.password}
                  onChange={(e) =>
                    setForm({ ...form, password: e.target.value })
                  }
                  placeholder={editing ? "Leave blank to keep" : ""}
                />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.inference_enabled}
                  onChange={(e) =>
                    setForm({ ...form, inference_enabled: e.target.checked })
                  }
                />
                Inference enabled
              </label>
              <div className="flex flex-1 items-center gap-2">
                <Label htmlFor="camera-fps" className="shrink-0">
                  FPS
                </Label>
                <Input
                  id="camera-fps"
                  type="number"
                  min={1}
                  max={30}
                  value={form.inference_fps}
                  onChange={(e) =>
                    setForm({ ...form, inference_fps: Number(e.target.value) })
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                Save
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
