import {
  AlertTriangle,
  FileText,
  LayoutDashboard,
  Map as MapIcon,
  MapPin,
  Radio,
  ScanSearch,
  Shield,
  Users,
  Video,
} from "lucide-react";
import type { IconComponent } from "@/lib/labels";

export interface NavItem {
  href: string;
  label: string;
  icon: IconComponent;
  adminOnly?: boolean;
  hotkey: string;
  mobile?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
    hotkey: "d",
    mobile: true,
  },
  { href: "/live", label: "Live", icon: Radio, hotkey: "l", mobile: true },
  {
    href: "/site",
    label: "Site",
    icon: MapIcon,
    hotkey: "s",
    mobile: false,
  },
  {
    href: "/detect",
    label: "Detect",
    icon: ScanSearch,
    hotkey: "t",
    mobile: true,
  },
  {
    href: "/incidents",
    label: "Incidents",
    icon: AlertTriangle,
    hotkey: "i",
    mobile: true,
  },
  {
    href: "/cameras",
    label: "Cameras",
    icon: Video,
    hotkey: "c",
    mobile: true,
  },
  { href: "/zones", label: "Zones", icon: MapPin, hotkey: "z" },
  { href: "/rules", label: "Rules", icon: Shield, hotkey: "r" },
  { href: "/users", label: "Users", icon: Users, adminOnly: true, hotkey: "u" },
  {
    href: "/audit",
    label: "Audit",
    icon: FileText,
    adminOnly: true,
    hotkey: "a",
  },
];

export function isNavActive(href: string, pathname: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function pageTitle(pathname: string): string {
  if (pathname === "/") return "Dashboard";
  const match = NAV_ITEMS.find(
    (item) => item.href !== "/" && pathname.startsWith(item.href),
  );
  if (pathname.startsWith("/live/capture")) return "Mobile capture";
  return match?.label ?? "Threat Recognition";
}
