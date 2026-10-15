export interface ClassInfo {
  label: string;
  short: string;
  category: string;
  threat: boolean;
}

const CLASS_INFO: Record<string, ClassInfo> = {
  firearm: {
    label: "Firearm (gun)",
    short: "Gun",
    category: "Weapon",
    threat: true,
  },
  melee_weapon: {
    label: "Melee weapon (knife / blade)",
    short: "Knife",
    category: "Weapon",
    threat: true,
  },
  explosive: {
    label: "Explosive device",
    short: "Explosive",
    category: "Explosive",
    threat: true,
  },
  blunt_weapon: {
    label: "Blunt weapon",
    short: "Blunt weapon",
    category: "Weapon",
    threat: true,
  },
  fire_smoke: {
    label: "Fire / smoke",
    short: "Fire",
    category: "Hazard",
    threat: true,
  },
  tool: { label: "Tool", short: "Tool", category: "Object", threat: false },
  person: {
    label: "Person",
    short: "Person",
    category: "Person",
    threat: false,
  },
  fall: {
    label: "Person down / fall",
    short: "Fall",
    category: "Behavior",
    threat: true,
  },
  violence: {
    label: "Violence",
    short: "Violence",
    category: "Behavior",
    threat: true,
  },
  crowd: {
    label: "Crowd",
    short: "Crowd",
    category: "Behavior",
    threat: false,
  },
};

export function classInfo(name: string): ClassInfo {
  return (
    CLASS_INFO[name] ?? {
      label: name.replace(/_/g, " "),
      short: name.replace(/_/g, " "),
      category: "Other",
      threat: false,
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

export function severityVariant(
  severity: string,
): "destructive" | "warning" | "secondary" | "info" {
  if (
    severity === "critical" ||
    severity === "very_high" ||
    severity === "high"
  )
    return "destructive";
  if (severity === "medium") return "warning";
  if (severity === "low") return "info";
  return "secondary";
}

export function statusVariant(
  status: string,
): "destructive" | "warning" | "secondary" | "success" | "info" {
  if (status === "verified") return "success";
  if (status === "dismissed" || status === "merged") return "secondary";
  if (status === "pending_review") return "warning";
  if (status === "detected") return "info";
  if (status === "notification_failed") return "destructive";
  return "secondary";
}

export function formatConfidence(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}
