from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SESSION_SECRET = "replace-this-local-session-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ION_PULSE_",
        extra="ignore",
    )

    app_name: str = "Ion Pulse API"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    site_url: str = "http://localhost:5173"
    database_url: str = "postgresql+asyncpg://ion_pulse:ion_pulse@localhost:5432/ion_pulse"
    cors_origins: list[str] = ["http://localhost:5173"]
    session_secret: str = DEFAULT_SESSION_SECRET
    session_cookie_name: str = "ion_pulse_session"
    session_lifetime_hours: int = 720
    session_cookie_secure: bool = False
    password_reset_lifetime_minutes: int = 30
    password_reset_delivery: Literal["log", "smtp"] = "log"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@ion-pulse.local"
    smtp_use_tls: bool = True
    ai_review_provider: Literal["none", "openai_compatible"] = "none"
    ai_review_api_base_url: str = "https://api.openai.com/v1"
    ai_review_api_key: str | None = None
    ai_review_model: str = "gpt-4.1-mini"
    ai_review_rules_version: str = "2026-07-01"
    translation_provider: Literal["none", "openai_compatible"] = "none"
    translation_api_base_url: str = "https://api.openai.com/v1"
    translation_api_key: str | None = None
    translation_model: str = "gpt-4.1-mini"
    worker_poll_seconds: int = 30
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_display_name: str = "admin"
    bootstrap_admin_reset_password: bool = False

    @model_validator(mode="after")
    def require_secure_production_settings(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.debug:
            raise ValueError("Production must not enable debug mode")
        if not self.site_url.startswith("https://"):
            raise ValueError("Production site URL must use HTTPS")
        if not self.session_cookie_secure:
            raise ValueError("Production requires secure session cookies")
        if self.session_secret == DEFAULT_SESSION_SECRET or len(self.session_secret) < 32:
            raise ValueError(
                "Production requires a unique session secret of at least 32 characters"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
