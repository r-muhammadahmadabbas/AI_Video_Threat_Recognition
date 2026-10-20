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
}

export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
    hotkey: "d",
  },
  { href: "/live", label: "Live", icon: Radio, hotkey: "l" },
  {
    href: "/site",
    label: "Site",
    icon: MapIcon,
    hotkey: "s",
  },
  {
    href: "/detect",
    label: "Detect",
    icon: ScanSearch,
    hotkey: "t",
  },
  {
    href: "/incidents",
    label: "Incidents",
    icon: AlertTriangle,
    hotkey: "i",
  },
  {
    href: "/cameras",
    label: "Cameras",
    icon: Video,
    hotkey: "c",
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
