from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ICEYARD_", env_file=".env", extra="ignore")

    app_name: str = "Iceyard"
    environment: Literal["local", "test", "staging", "production"] = "local"
    # Commercial edition gate. The OSS build (published on GitHub, BSL-licensed) runs
    # "oss"; the hosted SaaS at iceyard.dev runs "cloud"/"enterprise" to unlock paid
    # features. See iceyard_api/editions and LICENSING.md.
    edition: Literal["oss", "cloud", "enterprise"] = "oss"
    database_url: str = "sqlite:///./iceyard.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    cors_origin_regex: str | None = None
    session_ttl_minutes: int = 60 * 12
    log_level: str = "INFO"
    secure_cookies: bool = False
    secret_encryption_key: str | None = None
    # Security
    auth_rate_limit_attempts: int = 10
    auth_rate_limit_window_seconds: int = 60

    # Origins on a private LAN (e.g. http://192.168.x.x:3000) are common when the
    # console is opened from another device during local development. In local mode
    # we allow them via regex unless an explicit regex is configured.
    LOCAL_DEV_ORIGIN_REGEX: str = (
        r"^https?://("
        r"localhost|127\.0\.0\.1|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?$"
    )

    def effective_cors_origin_regex(self) -> str | None:
        """Explicit regex wins; otherwise allow LAN origins only in dev modes."""
        if self.cors_origin_regex:
            return self.cors_origin_regex
        if self.environment in {"local", "test"}:
            return self.LOCAL_DEV_ORIGIN_REGEX
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
