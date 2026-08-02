"""
Central application configuration, loaded from environment variables / .env.
Using pydantic-settings keeps config validated and typed instead of scattered
os.environ.get() calls across the codebase.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OceanGuardian AI MVP"
    environment: str = "development"

    database_url: str = "postgresql+psycopg2://oceanguardian:oceanguardian@localhost:5432/oceanguardian"

    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    cors_origins: str = "*"
    weather_provider: str = "open-meteo"

    # Location freshness thresholds (minutes since the last recorded ping)
    # used to compute LIVE/RECENT/LAST_KNOWN/STALE/UNKNOWN — see
    # app.services.tracking_service.compute_freshness. Configurable rather
    # than hardcoded so ops can tune them without a code change; the mobile
    # app's default capture interval is 5 minutes (app_config.dart), so
    # LIVE/RECENT default to loose multiples of that.
    freshness_live_minutes: int = 10
    freshness_recent_minutes: int = 30
    freshness_last_known_minutes: int = 180

    # Safety State Engine thresholds (0-100 score -> SAFE/MONITOR/CAUTION/
    # HIGH_RISK/CRITICAL). See app.services.safety_engine.
    safety_score_monitor: int = 21
    safety_score_caution: int = 41
    safety_score_high_risk: int = 61
    safety_score_critical: int = 81

    # Weather provider: "open-meteo" (real, no API key required — see
    # app.services.weather_service) or "simulated" (deterministic synthetic
    # data, clearly labeled, for offline dev/demo). Falls back to
    # WEATHER_DATA_UNAVAILABLE on a real provider failure — never silently
    # substitutes fake data for a failed real call.
    weather_http_timeout_seconds: float = 8.0

    # AI provider: "template" (deterministic, always available, default) or
    # "anthropic" (real LLM call — requires anthropic_api_key; falls back to
    # template automatically if the key is absent or the call fails).
    ai_provider: str = "template"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"

    # Notification provider: "simulation" (default — logs + records in DB,
    # clearly marked SIMULATION, no real message sent) or "twilio"/"smtp"
    # once real credentials are configured. See app.services.notification_service.
    notification_provider: str = "simulation"
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None

    # Notification Engine configuration
    notification_worker_concurrency: int = 4
    notification_worker_batch_size: int = 20
    notification_default_retry_policy: str = "exponential"  # exponential | linear
    notification_retry_jitter_seconds: int = 30
    notification_max_attempts: int = 10
    notification_queue_poll_interval_seconds: int = 5

    rate_limit_per_minute: int = 30

    # Set by scripts/demo_mode.{sh,ps1} — never set this in a real
    # deployment. Surfaced via GET /api/v1/system-info so the mobile app
    # and rescue dashboard can render a persistent "DEMO / SIMULATION
    # MODE" banner rather than letting demo data look indistinguishable
    # from a real deployment.
    demo_mode: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
