from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "sogetiong"
    environment: Literal["dev", "prod", "test"] = Field(
        default="dev",
        alias="APP_ENV",
    )
    database_url: str = "sqlite:///./sogetiong.db"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    refresh_token_expire_days: int = 7
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@hufs-match.local"
    cors_origins: str = "null,http://localhost:3000,http://127.0.0.1:5500"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    def validate_for_production(self) -> None:
        if self.environment != "prod":
            return
        if self.secret_key == "change-me-in-production":
            raise ValueError("SECRET_KEY must be changed in production")
        if self.database_url.startswith("sqlite"):
            raise ValueError("DATABASE_URL must use managed PostgreSQL in production")
        if self.cors_origins.strip() in {"", "null"}:
            raise ValueError("CORS_ORIGINS must contain the deployed frontend origin")


@lru_cache
def get_settings() -> Settings:
    return Settings()
