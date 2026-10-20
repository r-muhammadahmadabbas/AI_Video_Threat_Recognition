import type { ComponentType, SVGProps } from "react";
import {
  CircleCheck,
  CircleDashed,
  CircleOff,
  CircleX,
  Clock,
  GitMerge,
  Info,
  OctagonAlert,
  Radar,
  TriangleAlert,
  User,
} from "lucide-react";
import {
  BladeIcon,
  BluntIcon,
  CrowdIcon,
  ExplosiveIcon,
  FightIcon,
  FirearmIcon,
  FireSmokeIcon,
  LoiterIcon,
  PersonDownIcon,
  ToolIcon,
  ZoneBreachIcon,
} from "@/components/icons/threat-icons";

export type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

export interface ClassInfo {
  label: string;
  short: string;
  category: string;
  threat: boolean;
  icon: IconComponent;
}

const CLASS_INFO: Record<string, ClassInfo> = {
  firearm: {
    label: "Firearm (gun)",
    short: "Gun",
    category: "Weapon",
    threat: true,
    icon: FirearmIcon,
  },
  melee_weapon: {
    label: "Melee weapon (knife / blade)",
    short: "Knife",
    category: "Weapon",
    threat: true,
    icon: BladeIcon,
  },
  explosive: {
    label: "Explosive device",
    short: "Explosive",
    category: "Explosive",
    threat: true,
    icon: ExplosiveIcon,
  },
  blunt_weapon: {
    label: "Blunt weapon",
    short: "Blunt weapon",
    category: "Weapon",
    threat: true,
    icon: BluntIcon,
  },
  fire_smoke: {
    label: "Fire / smoke",
    short: "Fire",
    category: "Hazard",
    threat: true,
    icon: FireSmokeIcon,
  },
  tool: {
    label: "Tool",
    short: "Tool",
    category: "Object",
    threat: false,
    icon: ToolIcon,
  },
  person: {
    label: "Person",
    short: "Person",
    category: "Person",
    threat: false,
    icon: User,
  },
  fall: {
    label: "Person down / fall",
    short: "Fall",
    category: "Behavior",
    threat: true,
    icon: PersonDownIcon,
  },
  violence: {
    label: "Violence",
    short: "Violence",
    category: "Behavior",
    threat: true,
    icon: FightIcon,
  },
  fight: {
    label: "Physical altercation",
    short: "Fight",
    category: "Behavior",
    threat: true,
    icon: FightIcon,
  },
  restricted_zone_entry: {
    label: "Restricted zone entry",
    short: "Zone breach",
    category: "Behavior",
    threat: true,
    icon: ZoneBreachIcon,
  },
  crowd_anomaly: {
    label: "Abnormal crowd movement",
    short: "Crowd",
    category: "Behavior",
    threat: false,
    icon: CrowdIcon,
  },
  loitering: {
    label: "Loitering",
    short: "Loitering",
    category: "Behavior",
    threat: false,
    icon: LoiterIcon,
  },
  crowd: {
    label: "Crowd",
    short: "Crowd",
    category: "Behavior",
    threat: false,
    icon: CrowdIcon,
  },
};

export function classInfo(name: string): ClassInfo {
  return (
    CLASS_INFO[name] ?? {
      label: name.replace(/_/g, " "),
      short: name.replace(/_/g, " "),
      category: "Other",
      threat: false,
      icon: CircleDashed,
    }
  );
}

const RULE_LABELS: Record<string, string> = {
  weapon: "Weapon detected in zone",
  altercation: "Physical altercation",
  fight: "Physical altercation",
  violence_detected: "Violence detected",
  crowd_anomaly: "Abnormal crowd movement",
  person_down: "Person down / fall",
  fall: "Person down / fall",
  loitering: "Loitering",
  restricted_zone_entry: "Restricted zone entry",
};

export function ruleLabel(rule: string): string {
  return RULE_LABELS[rule] ?? rule.replace(/_/g, " ");
}

const RULE_ICONS: Record<string, IconComponent> = {
  weapon: FirearmIcon,
  altercation: FightIcon,
  fight: FightIcon,
  violence_detected: FightIcon,
  crowd_anomaly: CrowdIcon,
  person_down: PersonDownIcon,
  fall: PersonDownIcon,
  loitering: LoiterIcon,
  restricted_zone_entry: ZoneBreachIcon,
};

export function ruleIcon(rule: string): IconComponent | null {
  return RULE_ICONS[rule] ?? null;
}

export interface EventInfo {
  icon: IconComponent;
}

export function eventInfo(event: string): EventInfo {
  return { icon: ruleIcon(event) ?? classInfo(event).icon };
}

export interface SeverityInfo {
  token: string;
  icon: IconComponent;
  label: string;
}

const SEVERITY_INFO: Record<string, SeverityInfo> = {
  critical: { token: "sev-critical", icon: OctagonAlert, label: "Critical" },
  very_high: { token: "sev-critical", icon: OctagonAlert, label: "Very high" },
  high: { token: "sev-high", icon: TriangleAlert, label: "High" },
  medium: { token: "sev-medium", icon: CircleDashed, label: "Medium" },
  low: { token: "sev-low", icon: Info, label: "Low" },
};

export function severityInfo(severity: string): SeverityInfo {
  return (
    SEVERITY_INFO[severity] ?? {
      token: "neutral",
      icon: Info,
      label: severity.replace(/_/g, " ") || "Unknown",
    }
  );
}

export function severityVariant(
  severity: string,
): "destructive" | "warning" | "secondary" | "info" {
  const token = severityInfo(severity).token;
  if (token === "sev-critical") return "destructive";
  if (token === "sev-high" || token === "sev-medium") return "warning";
  if (token === "sev-low") return "info";
  return "secondary";
}

export interface StatusInfo {
  token: string;
  icon: IconComponent;
  label: string;
}

const STATUS_INFO: Record<string, StatusInfo> = {
  detected: { token: "info", icon: Radar, label: "New" },
  pending_review: { token: "warning", icon: Clock, label: "Pending review" },
  verified: { token: "ok", icon: CircleCheck, label: "Verified" },
  dismissed: { token: "neutral", icon: CircleOff, label: "Dismissed" },
  merged: { token: "neutral", icon: GitMerge, label: "Merged" },
  notification_failed: {
    token: "critical",
    icon: CircleX,
    label: "Notify failed",
  },
};

export function statusInfo(status: string): StatusInfo {
  return (
    STATUS_INFO[status] ?? {
      token: "neutral",
      icon: CircleDashed,
      label: status.replace(/_/g, " ") || "Unknown",
    }
  );
}

export function statusVariant(
  status: string,
): "destructive" | "warning" | "secondary" | "success" | "info" {
  const token = statusInfo(status).token;
  if (token === "ok") return "success";
  if (token === "critical") return "destructive";
  if (token === "warning") return "warning";
  if (token === "info") return "info";
  return "secondary";
}

export function formatConfidence(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}
