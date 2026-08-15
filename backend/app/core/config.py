from typing import Any, Dict, Optional
from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI Business Intelligence Platform"

    # Clerk integration settings
    CLERK_SECRET_KEY: Optional[str] = None
    CLERK_JWKS_URL: Optional[str] = None

    # Environment settings
    ENVIRONMENT: str = "development"
    NODE_ENV: Optional[str] = None
    APP_ENV: Optional[str] = None
    DEV_AUTH_BYPASS: bool = False

    @model_validator(mode="after")
    def validate_dev_auth_bypass(self) -> "Settings":
        env_vars = [self.ENVIRONMENT, self.NODE_ENV, self.APP_ENV]
        is_prod = any(v and v.strip().lower() == "production" for v in env_vars)
        if is_prod and self.DEV_AUTH_BYPASS:
            raise ValueError(
                "CRITICAL CONFIGURATION ERROR: DEV_AUTH_BYPASS cannot be enabled in a production environment!"
            )
        return self

    # JWT Authentication settings
    SECRET_KEY: str = Field(
        default="super-secret-key-ai-bi-platform-antigravity-90210"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

    # PostgreSQL database configurations
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "ai_bi_db"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str) and v:
            return v
        data = info.data
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=data.get("POSTGRES_USER"),
                password=data.get("POSTGRES_PASSWORD"),
                host=data.get("POSTGRES_SERVER"),
                port=data.get("POSTGRES_PORT"),
                path=data.get("POSTGRES_DB"),
            )
        )

    # Redis and Celery configurations
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def assemble_broker_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str) and v:
            return v
        data = info.data
        return f"redis://{data.get('REDIS_HOST')}:{data.get('REDIS_PORT')}/0"

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def assemble_backend_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str) and v:
            return v
        data = info.data
        return f"redis://{data.get('REDIS_HOST')}:{data.get('REDIS_PORT')}/0"

    # DuckDB path for analytical calculations
    DUCKDB_PATH: str = ":memory:"

    # ML Platform Retraining Schedules (in seconds)
    RETRAIN_INTERVAL_FORECAST: int = 86400
    RETRAIN_INTERVAL_CHURN: int = 86400
    RETRAIN_INTERVAL_SEGMENTATION: int = 86400
    RETRAIN_INTERVAL_ANOMALY: int = 86400

    # Production telemetry and logging
    LOG_FORMAT: str = "json"
    SENTRY_DSN: Optional[str] = None
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None

    # LLM and OpenRouter configurations
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_PROVIDER: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Production security
    ALLOWED_ORIGINS: str = "*"
    RATE_LIMIT_PER_MINUTE: int = 100
    API_KEYS: str = "admin-secret-api-key-12345,analyst-key-54321"


settings = Settings()

