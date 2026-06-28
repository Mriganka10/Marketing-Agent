from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Marketing Agent"
    environment: Literal["local", "staging", "production"] = "local"
    secret_key: str = Field(default="change-me-before-production")
    api_key: str | None = Field(default=None, description="Optional x-api-key for write APIs")

    database_url: str = "sqlite:///./data/marketing_agent.db"
    data_dir: Path = Path("./data")

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_enabled: bool = True

    allowed_origins: list[str] = ["*"]
    public_base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def can_use_openai(self) -> bool:
        return self.openai_enabled and bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings

