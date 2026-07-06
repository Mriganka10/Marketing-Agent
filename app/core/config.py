from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Marketing Agent"
    environment: Literal["local", "staging", "production"] = "local"
    secret_key: str = Field(default="change-me-before-production")
    api_key: str | None = Field(default=None, description="Optional x-api-key for write APIs")

    database_url: str = "sqlite:///./data/marketing_agent.db"
    data_dir: Path = Path("./data")

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"
    openai_reasoning_effort: str = "medium"
    openai_embedding_model: str = "text-embedding-3-large"
    openai_enabled: bool = True

    allowed_origins: list[str] = ["*"]
    public_base_url: str = "http://localhost:8000"
    ga4_measurement_id: str | None = None
    ga4_property_id: str | None = None
    google_search_console_site_url: str | None = None
    google_service_account_json: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def default_blank_database_url(cls, value: str | None) -> str:
        if not value:
            return "sqlite:///./data/marketing_agent.db"
        return value

    @field_validator("openai_model", mode="before")
    @classmethod
    def default_blank_openai_model(cls, value: str | None) -> str:
        if not value:
            return "gpt-5.5"
        return value

    @property
    def can_use_openai(self) -> bool:
        return self.openai_enabled and bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
