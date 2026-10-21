"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle,
  Download,
  FileText,
  Image as ImageIcon,
  Loader2,
  Video,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiErrorMessage, API_BASE, http } from "@/lib/api";
import { Evidence, Incident, Paginated } from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { useAuthenticatedBlob } from "@/hooks/use-authenticated-blob";
import { AuthenticatedImage } from "@/components/authenticated-image";
import { SeverityBadge, StatusBadge } from "@/components/status-badges";
import { EmptyState, ErrorState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useState } from "react";
import { eventInfo, ruleLabel, severityInfo } from "@/lib/labels";
import { cn } from "@/lib/utils";

function ConfidenceMeter({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${Math.min(100, value * 100)}%` }}
        />
      </div>
      <span className="font-mono text-sm tabular-nums">
        {(value * 100).toFixed(1)}%
      </span>
    </div>
  );
}

function EvidenceItem({ evidence }: { evidence: Evidence }) {
  const [downloading, setDownloading] = useState(false);
  const fileUrl = api.getEvidenceFile(evidence.id);
  const isVideo = evidence.evidence_type !== "snapshot";
  const { objectUrl } = useAuthenticatedBlob(isVideo ? fileUrl : null);

  const download = async () => {
    setDownloading(true);
    try {
      const relative = fileUrl.startsWith(API_BASE)
        ? fileUrl.slice(API_BASE.length)
        : fileUrl;
      const response = await http.get(relative, { responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `evidence-${evidence.id}.${isVideo ? "mp4" : "jpg"}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Download failed");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface-2/40">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          {isVideo ? (
            <Video className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <ImageIcon className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          <span className="font-medium capitalize">
            {evidence.evidence_type}
          </span>
          {evidence.duration_seconds != null && (
            <span>· {evidence.duration_seconds.toFixed(1)}s</span>
          )}
          {evidence.size_bytes != null && (
            <span>· {(evidence.size_bytes / 1024 / 1024).toFixed(2)} MB</span>
          )}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5"
          onClick={download}
          disabled={downloading}
        >
          {downloading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Download className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          Download
        </Button>
      </div>
      <div className="bg-black">
        {isVideo ? (
          objectUrl ? (
            <video src={objectUrl} controls className="w-full" />
          ) : (
            <Skeleton className="aspect-video w-full rounded-none" />
          )
        ) : (
          <AuthenticatedImage
            src={api.getEvidenceThumbnail(evidence.id)}
            alt="Evidence snapshot"
            className="aspect-video w-full object-cover"
          />
        )}
      </div>
    </div>
  );
}

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [actionPending, setActionPending] = useState<
    "verify" | "dismiss" | null
  >(null);

  const {
    data: incident,
    loading,
    error,
    refetch,
  } = useFetch<Incident>(() => api.getIncident(id), [id]);

  const { data: evidence } = useFetch<Paginated<Evidence>>(
    () => api.getEvidence(id),
    [id],
  );

  const handleVerify = async () => {
    setActionPending("verify");
    try {
      await api.verifyIncident(id, true);
      toast.success("Incident verified");
      refetch();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not verify incident"));
    } finally {
      setActionPending(null);
    }
  };

  const handleDismiss = async () => {
    setActionPending("dismiss");
    try {
      await api.dismissIncident(id);
      toast.success("Incident dismissed");
      refetch();
    } catch (err) {
      toast.error(apiErrorMessage(err, "Could not dismiss incident"));
    } finally {
      setActionPending(null);
    }
  };

  if (loading && !incident) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (error && !incident) {
    return <ErrorState message={error} />;
  }

  if (!incident) {
    return <EmptyState title="Incident not found" />;
  }

  const canAct =
    incident.status === "detected" || incident.status === "pending_review";

  const EventIcon = eventInfo(incident.event_type).icon;
  const SevIcon = severityInfo(incident.severity).icon;

  const details: { label: string; value: React.ReactNode }[] = [
    {
      label: "Severity",
      value: <SeverityBadge severity={incident.severity} />,
    },
    { label: "Status", value: <StatusBadge status={incident.status} /> },
    {
      label: "Confidence",
      value: <ConfidenceMeter value={incident.confidence} />,
    },
    {
      label: "Camera",
      value: (
        <span className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-xs">
          Cam #{incident.camera_id}
        </span>
      ),
    },
    {
      label: "Zone",
      value: incident.zone_id ? (
        <span className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-xs">
          Zone #{incident.zone_id}
        </span>
      ) : (
        <span className="text-sm text-muted-foreground">—</span>
      ),
    },
    {
      label: "Rule",
      value: incident.rule_id ? (
        <span className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-xs">
          Rule #{incident.rule_id}
        </span>
      ) : (
        <span className="text-sm text-muted-foreground">—</span>
      ),
    },
    {
      label: "Model version",
      value: (
        <span className="font-mono text-sm">
          {incident.model_version || "n/a"}
        </span>
      ),
    },
    {
      label: "Track IDs",
      value: (
        <span className="font-mono text-sm">
          {incident.track_ids.join(", ") || "n/a"}
        </span>
      ),
    },
    {
      label: "First seen",
      value: new Date(incident.first_seen_at).toLocaleString(),
    },
    {
      label: "Last seen",
      value: new Date(incident.last_seen_at).toLocaleString(),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-2">
          <Button
            asChild
            variant="ghost"
            size="icon"
            className="-ml-2 shrink-0"
          >
            <Link href="/incidents" aria-label="Back to incidents">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
          <div className="min-w-0">
            <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
              <SevIcon
                className={cn(
                  "h-5 w-5 shrink-0",
                  incident.severity === "critical" ||
                    incident.severity === "very_high"
                    ? "text-sev-critical"
                    : incident.severity === "high"
                      ? "text-sev-high"
                      : incident.severity === "medium"
                        ? "text-sev-medium"
                        : "text-sev-low",
                )}
                aria-hidden="true"
              />
              Incident #{incident.id}
            </h1>
            <p className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
              <EventIcon className="h-3.5 w-3.5" aria-hidden="true" />
              {ruleLabel(incident.event_type)} ·{" "}
              {new Date(incident.first_seen_at).toLocaleString()}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={incident.status} />
          <SeverityBadge severity={incident.severity} />
          {canAct && (
            <>
              <Button
                onClick={handleVerify}
                disabled={actionPending !== null}
                className="gap-1.5"
              >
                {actionPending === "verify" ? (
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <CheckCircle className="h-4 w-4" aria-hidden="true" />
                )}
                Verify
              </Button>
              <Button
                variant="outline"
                onClick={handleDismiss}
                disabled={actionPending !== null}
                className="gap-1.5"
              >
                {actionPending === "dismiss" ? (
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <XCircle className="h-4 w-4" aria-hidden="true" />
                )}
                Dismiss
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
              Evidence
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {!evidence || evidence.items.length === 0 ? (
              <EmptyState
                title="No evidence available"
                description="Clips and snapshots are attached when the evidence worker processes the event."
                icon={Video}
              />
            ) : (
              evidence.items.map((item) => (
                <EvidenceItem key={item.id} evidence={item} />
              ))
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
                Details
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                {details.map((detail) => (
                  <div key={detail.label}>
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                      {detail.label}
                    </p>
                    <div className="mt-1 text-sm">{detail.value}</div>
                  </div>
                ))}
              </div>

              {incident.verified_at && (
                <div className="border-t border-border pt-3">
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    {incident.status === "verified" ? "Verified" : "Dismissed"}{" "}
                    by
                  </p>
                  <p className="mt-1 text-sm">
                    User #{incident.verified_by_id} at{" "}
                    {new Date(incident.verified_at).toLocaleString()}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {incident.metadata_json &&
            Object.keys(incident.metadata_json).length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm uppercase tracking-wider text-muted-foreground">
                    <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                    Metadata
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="max-h-64 overflow-auto rounded-md border border-border bg-surface-2 p-3 font-mono text-xs">
                    {JSON.stringify(incident.metadata_json, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}
        </div>
      </div>
    </div>
  );
}
