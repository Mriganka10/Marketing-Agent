import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.aws_ssm import load_runtime_ssm


class Settings(BaseSettings):
    app_name: str = "Marketing Agent"
    environment: Literal["local", "staging", "production"] = "local"
    secret_key: str = Field(default="change-me-before-production")
    api_key: str | None = Field(default=None, description="Optional x-api-key for write APIs")

    aws_region: str = "ap-south-1"
    ssm_enabled: bool = False
    ssm_parameter_path: str = "/marketing-agent/prod"
    ssm_fail_fast: bool = True
    ssm_loaded_parameters: int = Field(default=0, exclude=True)

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
    google_sync_schedule_enabled: bool = True
    google_sync_schedule_time: str = "08:30"
    google_sync_schedule_timezone: str = "Asia/Kolkata"
    dataforseo_enabled: bool = False
    dataforseo_login: str | None = None
    dataforseo_password: str | None = None
    google_ads_enabled: bool = False
    google_ads_developer_token: str | None = None
    google_ads_client_id: str | None = None
    google_ads_client_secret: str | None = None
    google_ads_refresh_token: str | None = None
    google_ads_login_customer_id: str | None = None
    google_ads_customer_id: str | None = None
    google_ads_api_version: str = "v23"

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

    @property
    def can_use_dataforseo(self) -> bool:
        return self.dataforseo_enabled and bool(self.dataforseo_login and self.dataforseo_password)

    @property
    def can_use_google_ads(self) -> bool:
        return self.google_ads_enabled and bool(
            self.google_ads_developer_token
            and self.google_ads_client_id
            and self.google_ads_client_secret
            and self.google_ads_refresh_token
            and self.google_ads_customer_id
        )


@lru_cache
def get_settings() -> Settings:
    ssm = load_runtime_ssm()
    values = {
        **ssm.values,
        "aws_region": ssm.region,
        "ssm_enabled": ssm.enabled,
        "ssm_parameter_path": ssm.parameter_path,
        "ssm_loaded_parameters": ssm.parameter_count,
    }
    if isinstance(values.get("allowed_origins"), str):
        try:
            values["allowed_origins"] = json.loads(values["allowed_origins"])
        except json.JSONDecodeError as exc:
            raise RuntimeError("SSM allowed-origins must be a valid JSON array.") from exc
    settings = Settings(**values)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
