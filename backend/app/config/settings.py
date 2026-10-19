from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = "postgres"
    name: str = "threat_recognition"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"


class SQLiteSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SQLITE_", extra="ignore")

    path: str = "./data/threat_recognition.db"

    @property
    def url(self) -> str:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{self.path}"

    @property
    def sync_url(self) -> str:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.path}"


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 20

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_", extra="ignore")

    secret_key: str = "dev-secret-key-change-in-production-min-32-chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12


class ModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MODEL_", extra="ignore")

    weights_dir: str = "./models"
    detector_name: Literal["yolo26n", "yolo26s", "yolo26m", "yolo26l", "yolo26x"] = "yolo26n"
    detector_confidence: float = 0.25
    detector_iou: float = 0.45
    tracker_type: Literal["bytetrack", "botsort"] = "bytetrack"
    tracker_args: dict = Field(default_factory=dict)
    inference_device: Literal["cpu", "cuda", "mps"] = "cpu"
    inference_batch_size: int = 1
    inference_target_fps: float = 5.0
    weapon_detection_enabled: bool = False
    weapon_confidence: float = 0.25
    pose_fall_detection_enabled: bool = False
    violence_detection_enabled: bool = False


class VideoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VIDEO_", extra="ignore")

    media_dir: str = "./media"
    evidence_dir: str = "./media/evidence"
    clip_pre_seconds: float = 5.0
    clip_post_seconds: float = 5.0
    clip_max_duration: float = 30.0
    frame_buffer_size: int = 150
    rtsp_timeout: int = 10
    rtsp_reconnect_delay: float = 2.0
    rtsp_max_reconnect_delay: float = 60.0


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STORAGE_", extra="ignore")

    type: Literal["local", "s3"] = "local"
    local_path: str = "./media"
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_endpoint_url: str | None = None


class NotificationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTIFY_", extra="ignore")

    email_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_tls: bool = True
    from_email: str | None = None
    webhook_url: str | None = None


class PrivacySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRIVACY_", extra="ignore")

    enable_privacy_zones: bool = True
    mask_before_inference: bool = False
    mask_after_inference: bool = True
    blur_kernel_size: int = 51


class RetentionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RETENTION_", extra="ignore")

    evidence_days: int = 30
    incidents_days: int = 365
    audit_logs_days: int = 365
    cleanup_interval_hours: int = 24


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    sqlite: SQLiteSettings = Field(default_factory=SQLiteSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    notification: NotificationSettings = Field(default_factory=NotificationSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)

    @property
    def use_sqlite(self) -> bool:
        return self.environment == "development"

    @property
    def db_url(self) -> str:
        return self.sqlite.url if self.use_sqlite else self.database.url

    @property
    def db_sync_url(self) -> str:
        return self.sqlite.sync_url if self.use_sqlite else self.database.sync_url


settings = AppSettings()
