from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    database_url: str = "postgresql+asyncpg://ion_pulse:ion_pulse@localhost:5432/ion_pulse"
    cors_origins: list[str] = ["http://localhost:5173"]
    session_secret: str = "replace-this-local-session-secret"
    session_cookie_name: str = "ion_pulse_session"
    session_lifetime_hours: int = 720
    session_cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
