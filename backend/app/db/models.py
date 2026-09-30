import enum
from datetime import datetime

from app.db.base import Base
from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class User(Base):
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.VIEWER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    cameras = relationship("Camera", back_populates="owner")
    incidents = relationship("Incident", back_populates="verified_by")
    audit_logs = relationship("AuditLog", back_populates="user")


class CameraStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    CONNECTING = "connecting"


class CameraSourceType(str, enum.Enum):
    RTSP = "rtsp"
    FILE = "file"
    WEBCAM = "webcam"
    ONVIF = "onvif"


class Camera(Base):
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[CameraSourceType] = mapped_column(
        Enum(CameraSourceType), nullable=False
    )
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CameraStatus] = mapped_column(
        Enum(CameraStatus), default=CameraStatus.OFFLINE, nullable=False
    )
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    inference_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    inference_fps: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    owner = relationship("User", back_populates="cameras")
    zones = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="camera")
    health_snapshots = relationship("SystemHealthSnapshot", back_populates="camera")

    __table_args__ = (Index("ix_camera_status_active", "status", "is_active"),)


class ZoneType(str, enum.Enum):
    RESTRICTED = "restricted"
    LOITERING = "loitering"
    PRIVACY = "privacy"
    CROWD = "crowd"


class Zone(Base):
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("camera.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_type: Mapped[ZoneType] = mapped_column(Enum(ZoneType), nullable=False)
    polygon: Mapped[list[list[float]]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    camera = relationship("Camera", back_populates="zones")
    rules = relationship("ThreatRule", back_populates="zone")

    __table_args__ = (Index("ix_zone_camera_type", "camera_id", "zone_type"),)


class ThreatRuleType(str, enum.Enum):
    RESTRICTED_ZONE_ENTRY = "restricted_zone_entry"
    LOITERING = "loitering"
    PERSON_DOWN = "person_down"
    FIGHT = "fight"
    CROWD_ANOMALY = "crowd_anomaly"
    WEAPON = "weapon"


class ThreatRuleSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatRule(Base):
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("camera.id", ondelete="CASCADE"), nullable=False
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("zone.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[ThreatRuleType] = mapped_column(
        Enum(ThreatRuleType), nullable=False
    )
    severity: Mapped[ThreatRuleSeverity] = mapped_column(
        Enum(ThreatRuleSeverity), default=ThreatRuleSeverity.MEDIUM, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    camera = relationship("Camera", backref="rules")
    zone = relationship("Zone", back_populates="rules")
    incidents = relationship("Incident", back_populates="rule")


class IncidentStatus(str, enum.Enum):
    DETECTED = "detected"
    MERGED = "merged"
    PENDING_REVIEW = "pending_review"
    VERIFIED = "verified"
    DISMISSED = "dismissed"
    NOTIFICATION_SENT = "notification_sent"
    NOTIFICATION_FAILED = "notification_failed"


class Incident(Base):
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("camera.id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("zone.id", ondelete="SET NULL"), nullable=True
    )
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("threat_rule.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[ThreatRuleSeverity] = mapped_column(
        Enum(ThreatRuleSeverity), nullable=False
    )
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus),
        default=IncidentStatus.DETECTED,
        nullable=False,
        index=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    track_ids: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    snapshot_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    clip_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verified_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    notification_status: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    camera = relationship("Camera", back_populates="incidents")
    zone = relationship("Zone", backref="incidents")
    rule = relationship("ThreatRule", back_populates="incidents")
    verified_by = relationship("User", back_populates="incidents")
    evidence = relationship(
        "IncidentEvidence", back_populates="incident", cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification", back_populates="incident", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="incident")

    __table_args__ = (
        Index("ix_incident_camera_status_time", "camera_id", "status", "first_seen_at"),
        Index("ix_incident_event_type_time", "event_type", "first_seen_at"),
    )


class IncidentEvidence(Base):
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incident.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    uri: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    incident = relationship("Incident", back_populates="evidence")


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    PUSH = "push"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"


class Notification(Base):
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incident.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel), nullable=False
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    incident = relationship("Incident", back_populates="notifications")


class AuditAction(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    INCIDENT_VIEW = "incident_view"
    INCIDENT_VERIFY = "incident_verify"
    INCIDENT_DISMISS = "incident_dismiss"
    CAMERA_CREATE = "camera_create"
    CAMERA_UPDATE = "camera_update"
    CAMERA_DELETE = "camera_delete"
    ZONE_CREATE = "zone_create"
    ZONE_UPDATE = "zone_update"
    ZONE_DELETE = "zone_delete"
    RULE_CREATE = "rule_create"
    RULE_UPDATE = "rule_update"
    RULE_DELETE = "rule_delete"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    SETTINGS_CHANGE = "settings_change"
    EXPORT_DATA = "export_data"


class AuditLog(Base):
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    incident_id: Mapped[int | None] = mapped_column(
        ForeignKey("incident.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction), nullable=False, index=True
    )
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user = relationship("User", back_populates="audit_logs")
    incident = relationship("Incident", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_log_user_time", "user_id", "created_at"),
        Index("ix_audit_log_action_time", "action", "created_at"),
    )


class SystemHealthSnapshot(Base):
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("camera.id", ondelete="SET NULL"), nullable=True, index=True
    )
    component: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    camera = relationship("Camera", back_populates="health_snapshots")

    __table_args__ = (Index("ix_health_component_time", "component", "created_at"),)


class ModelVersion(Base):
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    weights_path: Mapped[str] = mapped_column(String(512), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_name_version"),
        Index("ix_model_active", "is_active"),
    )
