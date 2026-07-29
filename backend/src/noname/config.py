from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with compatibility aliases for the user's existing env file."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    session_storage: str = "sqlite"
    session_database_path: str = "runtime/replay.sqlite3"
    session_max_messages: int = Field(default=40, ge=8, le=200)
    session_retention_hours: int = Field(default=24, ge=1, le=720)
    session_cleanup_interval_seconds: int = Field(default=300, ge=30, le=86400)

    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY", "API_KEY"),
    )
    llm_base_url: str = Field(
        default="https://api.vveai.com/v1",
        validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL", "API_BASE"),
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL"),
    )
    llm_timeout_seconds: float = Field(default=35.0, ge=3, le=120)

    @field_validator("session_storage")
    @classmethod
    def validate_session_storage(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"memory", "sqlite"}:
            raise ValueError("SESSION_STORAGE must be either 'memory' or 'sqlite'")
        return normalized

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key.strip())

    @property
    def use_sqlite_sessions(self) -> bool:
        return self.session_storage == "sqlite"


@lru_cache
def get_settings() -> Settings:
    return Settings()
