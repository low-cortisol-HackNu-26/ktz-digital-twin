from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "KZ8A Telemetry Backend"
    database_url: str = "postgresql://postgres:postgres@postgres:5432/locomotive_twin"
    redis_url: str = "redis://redis:6379/0"
    redis_channel: str = "telemetry.events"
    schema_version: str = "1.0.0"
    ingest_source_default: str = "simulator"


settings = Settings()
