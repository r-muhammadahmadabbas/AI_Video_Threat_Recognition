"use client";

import { useState } from "react";
import { Edit, Loader2, Plus, Shield, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, apiErrorMessage } from "@/lib/api";
import { Camera, Paginated, ThreatRule, Zone } from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { SeverityBadge } from "@/components/status-badges";
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

const RULE_TYPES = [
  "restricted_zone_entry",
  "loitering",
  "person_down",
  "fight",
  "crowd_anomaly",
  "weapon",
];
const SEVERITIES = ["low", "medium", "high", "critical"];

interface RuleForm {
  name: string;
  camera_id: number;
  zone_id?: number;
  rule_type: string;
  severity: string;
  cooldown_seconds: number;
  config_json: Record<string, unknown>;
  is_active: boolean;
}

const emptyForm: RuleForm = {
  name: "",
  camera_id: 0,
  zone_id: undefined,
  rule_type: "restricted_zone_entry",
  severity: "medium",
  cooldown_seconds: 60,
  config_json: {},
  is_active: true,
};

export default function RulesPage() {
  const { data, loading, error, refetch } = useFetch<Paginated<ThreatRule>>(
    () => api.getRules({ page: 1, page_size: 50 }),
    [],
  );
  const { data: camerasData } = useFetch<Paginated<Camera>>(
    () => api.getCameras({ page_size: 100 }),
    [],
  );
  const { data: zonesData } = useFetch<Paginated<Zone>>(
    () => api.getZones({ page: 1, page_size: 100 }),
    [],
  );

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<ThreatRule | null>(null);
  const [form, setForm] = useState<RuleForm>(emptyForm);
  const [configText, setConfigText] = useState("{}");
  const [configError, setConfigError] = useState(false);
  const [saving, setSaving] = useState(false);

  const cameraName = (cameraId: number) =>
    camerasData?.items.find((camera) => camera.id === cameraId)?.name ??
    `Camera #${cameraId}`;
  const zoneName = (zoneId?: number | null) =>
    zoneId
      ? (zonesData?.items.find((zone) => zone.id === zoneId)?.name ??
        `Zone #${zoneId}`)
      : "—";

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setConfigText("{}");
    setConfigError(false);
    setOpen(true);
  };

  const openEdit = (rule: ThreatRule) => {
    setEditing(rule);
    setForm({
      name: rule.name,
      camera_id: rule.camera_id,
      zone_id: rule.zone_id ?? undefined,
      rule_type: rule.rule_type,
      severity: rule.severity,
      cooldown_seconds: rule.cooldown_seconds,
      config_json: rule.config_json ?? {},
      is_active: rule.is_active,
    });
    setConfigText(JSON.stringify(rule.config_json ?? {}, null, 2));
    setConfigError(false);
    setOpen(true);
  };

  const handleConfigChange = (value: string) => {
    setConfigText(value);
    try {
      const parsed = JSON.parse(value);
      setForm((prev) => ({ ...prev, config_json: parsed }));
      setConfigError(false);
    } catch {
      setConfigError(true);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (configError) {
      toast.error("Config JSON is not valid");
      return;
    }
    setSaving(true);
    try {
      const payload = { ...form, zone_id: form.zone_id ?? null };
      if (editing) {
        await api.updateRule(editing.id, payload);
        toast.success("Rule updated");
      } else {
        await api.createRule(payload);
        toast.success("Rule created");
      }
      setOpen(false);
      refetch();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not save rule"));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (rule: ThreatRule) => {
    if (!window.confirm(`Delete rule "${rule.name}"?`)) return;
    try {
      await api.deleteRule(rule.id);
      toast.success("Rule deleted");
      refetch();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not delete rule"));
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Threat Rules</h1>
          <p className="text-sm text-muted-foreground">
            Configure detection rules for each camera
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add Rule
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
              title="No rules configured"
              description="Add rules to trigger incidents for weapons, loitering, falls and more."
              icon={Shield}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Name</TableHeaderCell>
                  <TableHeaderCell>Camera</TableHeaderCell>
                  <TableHeaderCell>Zone</TableHeaderCell>
                  <TableHeaderCell>Type</TableHeaderCell>
                  <TableHeaderCell>Severity</TableHeaderCell>
                  <TableHeaderCell>Cooldown</TableHeaderCell>
                  <TableHeaderCell>Active</TableHeaderCell>
                  <TableHeaderCell className="text-right">
                    Actions
                  </TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell className="font-medium">{rule.name}</TableCell>
                    <TableCell>{cameraName(rule.camera_id)}</TableCell>
                    <TableCell>{zoneName(rule.zone_id)}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="capitalize">
                        {rule.rule_type.replace(/_/g, " ")}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <SeverityBadge severity={rule.severity} />
                    </TableCell>
                    <TableCell>{rule.cooldown_seconds}s</TableCell>
                    <TableCell>
                      <Badge variant={rule.is_active ? "success" : "secondary"}>
                        {rule.is_active ? "Yes" : "No"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openEdit(rule)}
                        title="Edit"
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(rule)}
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Rule" : "Add Rule"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="rule-name">Name</Label>
              <Input
                id="rule-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Zone (optional)</Label>
                <Select
                  value={form.zone_id ? String(form.zone_id) : "none"}
                  onValueChange={(value) =>
                    setForm({
                      ...form,
                      zone_id: value === "none" ? undefined : Number(value),
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="No zone" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No zone</SelectItem>
                    {zonesData?.items.map((zone) => (
                      <SelectItem key={zone.id} value={String(zone.id)}>
                        {zone.name} ({zone.zone_type})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label>Rule type</Label>
                <Select
                  value={form.rule_type}
                  onValueChange={(value) =>
                    setForm({ ...form, rule_type: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {RULE_TYPES.map((type) => (
                      <SelectItem
                        key={type}
                        value={type}
                        className="capitalize"
                      >
                        {type.replace(/_/g, " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Severity</Label>
                <Select
                  value={form.severity}
                  onValueChange={(value) =>
                    setForm({ ...form, severity: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SEVERITIES.map((severity) => (
                      <SelectItem
                        key={severity}
                        value={severity}
                        className="capitalize"
                      >
                        {severity}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="rule-cooldown">Cooldown (seconds)</Label>
              <Input
                id="rule-cooldown"
                type="number"
                min={0}
                max={3600}
                value={form.cooldown_seconds}
                onChange={(e) =>
                  setForm({ ...form, cooldown_seconds: Number(e.target.value) })
                }
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="rule-config">Config (JSON)</Label>
              <textarea
                id="rule-config"
                value={configText}
                onChange={(e) => handleConfigChange(e.target.value)}
                spellCheck={false}
                className={`min-h-[90px] w-full rounded-md border bg-background px-3 py-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring ${
                  configError ? "border-red-500" : "border-input"
                }`}
              />
              {configError && (
                <p className="text-xs text-red-500">Invalid JSON</p>
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
