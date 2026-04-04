# Pydantic Settings v2 configuration class.
#
# class Settings(BaseSettings):
#   DATABASE_URL: str
#   REDIS_URL: str
#   SECRET_KEY: str              # HS256 signing key for JWT issuance; min 32 chars
#   ALLOWED_ORIGINS: list[str]
#   CELERY_BROKER_URL: str
#   CELERY_RESULT_BACKEND: str
#   LOG_LEVEL: str = "info"
#   THRESHOLDS_PATH: str = "/app/shared/thresholds.json"
#   HISTORY_RETENTION_HOURS: int = 72
#   WS_MAX_CLIENTS_PER_LOCO: int = 50
#   TOKEN_LIFETIME_HOURS: int = 8    # one operator shift
#
#   model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
#
# settings = Settings()   # module-level singleton, imported everywhere
