from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    tz: str = Field(default="Asia/Krasnoyarsk", alias="TZ")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/job_matcher",
        alias="DATABASE_URL",
    )
    async_database_url: str = Field(
        default="postgresql+psycopg_async://postgres:postgres@localhost:5432/job_matcher",
        alias="ASYNC_DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    telegram_enabled: bool = Field(default=False, alias="TELEGRAM_ENABLED")
    telegram_source_enabled: bool = Field(default=False, alias="TELEGRAM_SOURCE_ENABLED")
    telegram_source_channels_raw: str = Field(default="", alias="TELEGRAM_SOURCE_CHANNELS")
    telegram_tdlib_api_id: int = Field(default=0, alias="TELEGRAM_TDLIB_API_ID")
    telegram_tdlib_api_hash: str = Field(default="", alias="TELEGRAM_TDLIB_API_HASH")
    telegram_tdlib_phone_number: str = Field(default="", alias="TELEGRAM_TDLIB_PHONE_NUMBER")
    telegram_tdlib_auth_code: str = Field(default="", alias="TELEGRAM_TDLIB_AUTH_CODE")
    telegram_tdlib_password: str = Field(default="", alias="TELEGRAM_TDLIB_PASSWORD")
    telegram_tdlib_db_dir: Path = Field(default=Path("./.tdlib"), alias="TELEGRAM_TDLIB_DB_DIR")
    telegram_tdlib_files_dir: Path = Field(
        default=Path("./.tdlib-files"), alias="TELEGRAM_TDLIB_FILES_DIR"
    )
    telegram_tdlib_encryption_key: str = Field(
        default="", alias="TELEGRAM_TDLIB_ENCRYPTION_KEY"
    )
    telegram_tdjson_lib_path: str = Field(default="", alias="TELEGRAM_TDJSON_LIB_PATH")

    collect_interval_minutes: int = Field(default=20, alias="COLLECT_INTERVAL_MINUTES")
    match_score_threshold: int = Field(default=70, alias="MATCH_SCORE_THRESHOLD")
    enable_scheduler: bool = Field(default=True, alias="ENABLE_SCHEDULER")
    enable_demo_mode: bool = Field(default=True, alias="ENABLE_DEMO_MODE")
    enable_experimental_adapters: bool = Field(
        default=False, alias="ENABLE_EXPERIMENTAL_ADAPTERS"
    )

    hh_api_base_url: str = Field(default="https://api.hh.ru", alias="HH_API_BASE_URL")
    superjob_api_key: str = Field(default="", alias="SUPERJOB_API_KEY")
    request_timeout_seconds: float = Field(default=20.0, alias="REQUEST_TIMEOUT_SECONDS")
    request_retries: int = Field(default=3, alias="REQUEST_RETRIES")
    request_backoff_seconds: float = Field(default=1.0, alias="REQUEST_BACKOFF_SECONDS")
    http_user_agent: str = Field(
        default="ai-job-aggregator/0.1 (+local-mvp)", alias="HTTP_USER_AGENT"
    )

    scoring_rules_path: Path = Field(
        default=Path("./config/scoring_rules.yaml"), alias="SCORING_RULES_PATH"
    )
    mcp_host: str = Field(default="0.0.0.0", alias="MCP_HOST")
    mcp_port: int = Field(default=8001, alias="MCP_PORT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_telegram_source_channels(settings: Settings) -> list[str]:
    raw = settings.telegram_source_channels_raw.strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]
