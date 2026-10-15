"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle,
  Download,
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
    <div className="rounded-lg border border-border p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <span className="rounded bg-muted px-2 py-0.5 text-xs font-medium capitalize">
          {evidence.evidence_type}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={download}
            disabled={downloading}
          >
            {downloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Download
          </Button>
        </div>
      </div>
      {isVideo ? (
        objectUrl ? (
          <video
            src={objectUrl}
            controls
            className="w-full rounded-md border border-border"
          />
        ) : (
          <Skeleton className="aspect-video w-full" />
        )
      ) : (
        <AuthenticatedImage
          src={api.getEvidenceThumbnail(evidence.id)}
          alt="Evidence snapshot"
          className="aspect-video w-full object-cover"
        />
      )}
      <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
        {evidence.duration_seconds != null && (
          <span>Duration: {evidence.duration_seconds.toFixed(1)}s</span>
        )}
        {evidence.size_bytes != null && (
          <span>Size: {(evidence.size_bytes / 1024 / 1024).toFixed(2)} MB</span>
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

  const details: { label: string; value: React.ReactNode }[] = [
    {
      label: "Event type",
      value: (
        <span className="capitalize">
          {incident.event_type.replace(/_/g, " ")}
        </span>
      ),
    },
    {
      label: "Severity",
      value: <SeverityBadge severity={incident.severity} />,
    },
    { label: "Status", value: <StatusBadge status={incident.status} /> },
    {
      label: "Confidence",
      value: (
        <span className="font-mono">
          {(incident.confidence * 100).toFixed(1)}%
        </span>
      ),
    },
    { label: "Camera", value: `Camera #${incident.camera_id}` },
    {
      label: "Zone",
      value: incident.zone_id ? `Zone #${incident.zone_id}` : "N/A",
    },
    {
      label: "Rule",
      value: incident.rule_id ? `Rule #${incident.rule_id}` : "N/A",
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
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Button asChild variant="ghost" size="sm" className="mb-2 -ml-2">
            <Link href="/incidents">
              <ArrowLeft className="h-4 w-4" />
              Incidents
            </Link>
          </Button>
          <h1 className="text-2xl font-bold">Incident #{incident.id}</h1>
          <p className="text-sm capitalize text-muted-foreground">
            {incident.event_type.replace(/_/g, " ")} ·{" "}
            {new Date(incident.first_seen_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={incident.status} />
          <SeverityBadge severity={incident.severity} />
          {canAct && (
            <>
              <Button onClick={handleVerify} disabled={actionPending !== null}>
                {actionPending === "verify" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle className="h-4 w-4" />
                )}
                Verify
              </Button>
              <Button
                variant="outline"
                onClick={handleDismiss}
                disabled={actionPending !== null}
              >
                {actionPending === "dismiss" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <XCircle className="h-4 w-4" />
                )}
                Dismiss
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Evidence</CardTitle>
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

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Details</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              {details.map((detail) => (
                <div key={detail.label}>
                  <p className="text-xs text-muted-foreground">
                    {detail.label}
                  </p>
                  <p className="mt-0.5 text-sm">{detail.value}</p>
                </div>
              ))}
            </div>

            {incident.verified_at && (
              <div className="border-t border-border pt-3">
                <p className="text-xs text-muted-foreground">
                  {incident.status === "verified" ? "Verified" : "Dismissed"} by
                </p>
                <p className="text-sm">
                  User #{incident.verified_by_id} at{" "}
                  {new Date(incident.verified_at).toLocaleString()}
                </p>
              </div>
            )}

            {incident.metadata_json &&
              Object.keys(incident.metadata_json).length > 0 && (
                <div className="border-t border-border pt-3">
                  <p className="mb-1 text-xs text-muted-foreground">Metadata</p>
                  <pre className="max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs">
                    {JSON.stringify(incident.metadata_json, null, 2)}
                  </pre>
                </div>
              )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
