"use client";

import { useState } from "react";
import { History, Search } from "lucide-react";
import { api } from "@/lib/api";
import { AuditLog, Paginated } from "@/types";
import { useFetch } from "@/hooks/use-fetch";
import { EmptyState, ErrorState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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

const ACTIONS = [
  "login",
  "logout",
  "incident_view",
  "incident_verify",
  "incident_dismiss",
  "camera_create",
  "camera_update",
  "camera_delete",
  "zone_create",
  "zone_update",
  "zone_delete",
  "rule_create",
  "rule_update",
  "rule_delete",
  "user_create",
  "user_update",
  "user_delete",
  "settings_change",
  "export_data",
];

export default function AuditPage() {
  const [pendingAction, setPendingAction] = useState("all");
  const [pendingResource, setPendingResource] = useState("");
  const [pendingFrom, setPendingFrom] = useState("");
  const [pendingTo, setPendingTo] = useState("");

  const [filters, setFilters] = useState({
    action: "all",
    resource_type: "",
    date_from: "",
    date_to: "",
    page: 1,
  });

  const pageSize = 50;
  const { data, loading, error } = useFetch<Paginated<AuditLog>>(
    () =>
      api.getAuditLogs({
        action: filters.action === "all" ? undefined : filters.action,
        resource_type: filters.resource_type || undefined,
        date_from: filters.date_from
          ? new Date(filters.date_from).toISOString()
          : undefined,
        date_to: filters.date_to
          ? new Date(filters.date_to).toISOString()
          : undefined,
        page: filters.page,
        page_size: pageSize,
      }),
    [filters],
  );

  const applyFilters = () => {
    setFilters({
      action: pendingAction,
      resource_type: pendingResource.trim(),
      date_from: pendingFrom,
      date_to: pendingTo,
      page: 1,
    });
  };

  const clearFilters = () => {
    setPendingAction("all");
    setPendingResource("");
    setPendingFrom("");
    setPendingTo("");
    setFilters({
      action: "all",
      resource_type: "",
      date_from: "",
      date_to: "",
      page: 1,
    });
  };

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Audit Log</h1>
        <p className="text-sm text-muted-foreground">
          Track user activity across the system
        </p>
      </div>

      {error && <ErrorState message={error} />}

      <Card>
        <CardContent className="p-5">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              applyFilters();
            }}
            className="flex flex-wrap items-end gap-3"
          >
            <div className="flex min-w-[160px] flex-1 flex-col gap-2">
              <Label>Action</Label>
              <Select value={pendingAction} onValueChange={setPendingAction}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All actions</SelectItem>
                  {ACTIONS.map((action) => (
                    <SelectItem
                      key={action}
                      value={action}
                      className="capitalize"
                    >
                      {action.replace(/_/g, " ")}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex min-w-[160px] flex-1 flex-col gap-2">
              <Label htmlFor="audit-resource">Resource type</Label>
              <Input
                id="audit-resource"
                value={pendingResource}
                onChange={(e) => setPendingResource(e.target.value)}
                placeholder="camera, user, ..."
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="audit-from">From</Label>
              <Input
                id="audit-from"
                type="datetime-local"
                value={pendingFrom}
                onChange={(e) => setPendingFrom(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="audit-to">To</Label>
              <Input
                id="audit-to"
                type="datetime-local"
                value={pendingTo}
                onChange={(e) => setPendingTo(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={loading}>
              <Search className="h-4 w-4" />
              Apply
            </Button>
            <Button type="button" variant="ghost" onClick={clearFilters}>
              Clear
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-5">
          {loading && !data ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-10" />
              ))}
            </div>
          ) : !data || data.items.length === 0 ? (
            <EmptyState
              title="No audit entries"
              description="Activity will appear here as users interact with the system."
              icon={History}
            />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHeaderCell>Time</TableHeaderCell>
                    <TableHeaderCell>User</TableHeaderCell>
                    <TableHeaderCell>Action</TableHeaderCell>
                    <TableHeaderCell>Resource</TableHeaderCell>
                    <TableHeaderCell>IP</TableHeaderCell>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                        {new Date(log.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        {log.user_id ? `#${log.user_id}` : "system"}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="capitalize">
                          {log.action.replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {log.resource_type
                          ? `${log.resource_type}${
                              log.resource_id ? ` #${log.resource_id}` : ""
                            }`
                          : "—"}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {log.ip_address || "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
                <span>
                  {data.total} entr{data.total === 1 ? "y" : "ies"}
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={filters.page <= 1}
                    onClick={() =>
                      setFilters((prev) => ({ ...prev, page: prev.page - 1 }))
                    }
                  >
                    Previous
                  </Button>
                  <span>
                    Page {filters.page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={filters.page >= totalPages}
                    onClick={() =>
                      setFilters((prev) => ({ ...prev, page: prev.page + 1 }))
                    }
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
