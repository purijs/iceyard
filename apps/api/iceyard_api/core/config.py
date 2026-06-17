from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ICEYARD_", env_file=".env", extra="ignore")

    app_name: str = "Iceyard"
    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = "sqlite:///./iceyard.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    session_ttl_minutes: int = 60 * 12
    log_level: str = "INFO"
    secure_cookies: bool = False
    enable_dev_seed: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
