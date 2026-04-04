from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/locomotive_twin"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = Field(
        default="change-me-in-production-min-32-chars!!",
        validation_alias="JWT_SECRET",
    )
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    LOG_LEVEL: str = "info"
    THRESHOLDS_PATH: str = "/app/shared/thresholds.json"
    HISTORY_RETENTION_HOURS: int = 72
    WS_MAX_CLIENTS_PER_LOCO: int = 50
    TOKEN_LIFETIME_HOURS: int = 8
    REFRESH_TOKEN_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
