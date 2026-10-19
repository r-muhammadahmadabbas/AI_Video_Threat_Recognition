"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Eye,
  Search,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { IncidentListResponse } from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { SeverityBadge, StatusBadge } from "@/components/status-badges";
import { EmptyState, ErrorState } from "@/components/empty-state";
import { classInfo, eventInfo, ruleLabel, severityInfo } from "@/lib/labels";
import { timeAgo } from "@/lib/time";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { cn } from "@/lib/utils";

const SEVERITIES = ["critical", "high", "medium", "low"];
const STATUSES = [
  "detected",
  "pending_review",
  "verified",
  "dismissed",
  "merged",
];

export default function IncidentsPage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");

  const { data, loading, error, refetch } = useFetch<IncidentListResponse>(
    () =>
      api.getIncidents({
        page,
        page_size: pageSize,
        event_type: search || undefined,
        severity: severity || undefined,
        status: status || undefined,
      }),
    [page, search, severity, status],
  );

  useEffect(() => {
    const interval = setInterval(refetch, 5000);
    return () => clearInterval(interval);
  }, [refetch]);

  const totalPages = useMemo(
    () => (data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1),
    [data],
  );

  const hasFilters = severity !== "" || status !== "" || search !== "";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Incidents</h1>
          <p className="text-sm text-muted-foreground">
            Review and manage security incidents
          </p>
        </div>
        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-muted-foreground"
            onClick={() => {
              setSearch("");
              setSeverity("");
              setStatus("");
              setPage(1);
            }}
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            Clear filters
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 p-4 md:p-5">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative w-full sm:w-64">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                placeholder="Search incidents…"
                aria-label="Search incidents"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(1);
                }}
                className="pl-8"
              />
            </div>
            <Select
              value={status || "all"}
              onValueChange={(value) => {
                setStatus(value === "all" ? "" : value);
                setPage(1);
              }}
            >
              <SelectTrigger
                className="w-full sm:w-44"
                aria-label="Filter by status"
              >
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {STATUSES.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item.replace(/_/g, " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div
              className="flex flex-wrap items-center gap-1.5"
              role="group"
              aria-label="Filter by severity"
            >
              <button
                type="button"
                onClick={() => {
                  setSeverity("");
                  setPage(1);
                }}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                  severity === ""
                    ? "border-primary/50 bg-primary/15 text-primary"
                    : "border-border-strong bg-surface-2 text-muted-foreground hover:text-foreground",
                )}
              >
                All
              </button>
              {SEVERITIES.map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => {
                    setSeverity(item);
                    setPage(1);
                  }}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                    severity === item
                      ? "border-primary/50 bg-primary/15 text-primary"
                      : "border-border-strong bg-surface-2 text-muted-foreground hover:text-foreground",
                  )}
                >
                  {severityInfo(item).label}
                </button>
              ))}
            </div>
          </div>

          {error && <ErrorState message={error} />}

          {loading && !data ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-12" />
              ))}
            </div>
          ) : !data || data.items.length === 0 ? (
            <EmptyState
              title="No incidents found"
              description="Detected threats appear here for operator review."
              icon={AlertTriangle}
            />
          ) : (
            <div className="max-h-[65vh] overflow-auto rounded-lg border border-border">
              <Table>
                <TableHeader className="sticky top-0 z-10 bg-surface-1">
                  <TableRow>
                    <TableHeaderCell>Time</TableHeaderCell>
                    <TableHeaderCell>Event</TableHeaderCell>
                    <TableHeaderCell>Severity</TableHeaderCell>
                    <TableHeaderCell>Status</TableHeaderCell>
                    <TableHeaderCell>Confidence</TableHeaderCell>
                    <TableHeaderCell>Camera</TableHeaderCell>
                    <TableHeaderCell className="text-right">
                      Actions
                    </TableHeaderCell>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((incident) => {
                    const EventIcon = eventInfo(incident.event_type).icon;
                    const threat = classInfo(incident.event_type).threat;
                    return (
                      <TableRow key={incident.id}>
                        <TableCell className="whitespace-nowrap">
                          <span
                            className="text-sm"
                            title={new Date(
                              incident.first_seen_at,
                            ).toLocaleString()}
                          >
                            {timeAgo(incident.first_seen_at)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex min-w-0 items-center gap-2.5">
                            <EventIcon
                              className={cn(
                                "h-4 w-4 shrink-0",
                                threat
                                  ? "text-sev-high"
                                  : "text-muted-foreground",
                              )}
                              aria-hidden="true"
                            />
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">
                                {ruleLabel(incident.event_type)}
                              </p>
                              <p className="font-mono text-[11px] text-muted-foreground">
                                #{incident.id}
                              </p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <SeverityBadge severity={incident.severity} />
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={incident.status} />
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <div className="h-1 w-16 overflow-hidden rounded-full bg-surface-3">
                              <div
                                className="h-full rounded-full bg-primary"
                                style={{
                                  width: `${Math.min(100, incident.confidence * 100)}%`,
                                }}
                              />
                            </div>
                            <span className="font-mono text-xs tabular-nums">
                              {(incident.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="rounded-md border border-border bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
                            Cam #{incident.camera_id}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button asChild variant="outline" size="sm">
                            <Link
                              href={`/incidents/${incident.id}`}
                              aria-label={`View incident ${incident.id}`}
                            >
                              <Eye className="h-4 w-4" aria-hidden="true" />
                              View
                            </Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs text-muted-foreground">
              {data && data.total > 0
                ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, data.total)} of ${data.total}`
                : "0 incidents"}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="icon"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </Button>
              <span className="font-mono text-xs tabular-nums text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
