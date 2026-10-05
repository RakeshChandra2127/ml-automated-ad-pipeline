import functools
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    APP_NAME: str = "AdEventTracker"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./adevent.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    AI_PROVIDER: Literal['openai', 'anthropic'] = 'openai'
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4o-mini"
    AI_TIMEOUT_SECONDS: int = 15

    RATE_LIMIT_MAX_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    BLOOM_FILTER_CAPACITY: int = 1000000
    BLOOM_FILTER_ERROR_RATE: float = 0.01

    CONSUMER_BATCH_SIZE: int = 100
    FRAUD_ANALYSIS_INTERVAL_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@functools.lru_cache
def get_settings() -> Settings:
    """Returns a cached instance of the settings."""
    return Settings()
