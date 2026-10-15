export interface DetectionResult {
  timestamp: number;
  class_name: string;
  confidence: number;
  bbox: number[];
  is_threat: boolean;
  track_id: number;
  weapon: boolean;
  weapon_conf: number;
  fall?: boolean;
  violence?: boolean;
  frame_image?: string | null;
}

export interface RuleTrigger {
  rule: string;
  severity: string;
  timestamp: number;
  tracker_ids: number[];
  details: Record<string, unknown>;
}

export interface DetectionResponse {
  total_frames: number;
  detections: DetectionResult[];
  events: RuleTrigger[];
}

export interface User {
  id: number;
  email: string;
  full_name: string | null;
  role: "admin" | "operator" | "viewer";
  is_active: boolean;
  last_login_at?: string | null;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface DashboardStats {
  total_cameras: number;
  online_cameras: number;
  total_incidents: number;
  pending_incidents: number;
  verified_incidents: number;
  dismissed_incidents: number;
  very_high_risk_incidents: number;
  incidents_last_24h: number;
}

export interface Incident {
  id: number;
  camera_id: number;
  zone_id?: number | null;
  rule_id?: number | null;
  event_type: string;
  severity: string;
  status: string;
  first_seen_at: string;
  last_seen_at: string;
  confidence: number;
  model_version: string;
  rule_version: number;
  track_ids: number[];
  snapshot_uri?: string | null;
  clip_uri?: string | null;
  verified_by_id?: number | null;
  verified_at?: string | null;
  notification_status?: string | null;
  metadata_json: Record<string, unknown>;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentListResponse {
  items: Incident[];
  total: number;
  page: number;
  page_size: number;
}

export interface Camera {
  id: number;
  name: string;
  source_type: string;
  source_url: string;
  status: string;
  username?: string | null;
  inference_enabled?: boolean;
  inference_fps?: number;
  width?: number | null;
  height?: number | null;
  is_active?: boolean;
  confidence?: number;
  created_at: string;
}

export interface PolygonPoint {
  x: number;
  y: number;
}

export type Polygon = PolygonPoint[][];

export interface Zone {
  id: number;
  camera_id: number;
  name: string;
  zone_type: string;
  polygon: Polygon;
  is_active: boolean;
  created_at?: string;
}

export interface ThreatRule {
  id: number;
  name: string;
  camera_id: number;
  zone_id?: number | null;
  rule_type: string;
  severity: string;
  is_active: boolean;
  config_json: Record<string, unknown>;
  cooldown_seconds: number;
  model_version?: string | null;
}

export interface Evidence {
  id: number;
  incident_id: number;
  evidence_type: string;
  duration_seconds?: number | null;
  size_bytes?: number | null;
  thumbnail_uri?: string | null;
  created_at: string;
}

export interface AuditLog {
  id: number;
  user_id?: number | null;
  incident_id?: number | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | number | null;
  details_json?: Record<string, unknown>;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
