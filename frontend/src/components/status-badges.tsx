import { Badge } from "@/components/ui/badge";
import { severityVariant, statusVariant } from "@/lib/labels";

export function SeverityBadge({ severity }: { severity: string }) {
  return (
    <Badge variant={severityVariant(severity)} className="capitalize">
      {severity.replace(/_/g, " ")}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={statusVariant(status)} className="capitalize">
      {status.replace(/_/g, " ")}
    </Badge>
  );
}
