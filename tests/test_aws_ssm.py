from __future__ import annotations

import pytest

from app.core.config import get_settings


class FakeSsmClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_parameters_by_path(self, **request):
        self.calls.append(request)
        if "NextToken" not in request:
            return {
                "Parameters": [
                    {
                        "Name": "/marketing-agent/prod/openai-api-key",
                        "Value": "ssm-openai-key",
                    },
                    {
                        "Name": "/marketing-agent/prod/database-url",
                        "Value": "postgresql+psycopg://ssm-user:ssm-pass@db/app",
                    },
                    {
                        "Name": "/marketing-agent/prod/allowed-origins",
                        "Value": '["https://app.example.com"]',
                    },
                ],
                "NextToken": "page-2",
            }
        return {
            "Parameters": [
                {"Name": "/marketing-agent/prod/secret-key", "Value": "ssm-secret"},
                {"Name": "/marketing-agent/prod/openai-enabled", "Value": "true"},
            ]
        }


def test_runtime_ssm_decrypts_pages_and_overrides_environment(monkeypatch):
    fake_client = FakeSsmClient()
    client_calls: list[dict[str, object]] = []

    def fake_boto_client(service_name: str, **kwargs):
        client_calls.append({"service_name": service_name, **kwargs})
        return fake_client

    monkeypatch.setenv("SSM_ENABLED", "true")
    monkeypatch.setenv("SSM_PARAMETER_PATH", "/marketing-agent/prod/")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("OPENAI_API_KEY", "stale-eb-key")
    monkeypatch.setenv("SECRET_KEY", "stale-eb-secret")
    monkeypatch.setattr("app.core.aws_ssm.boto3.client", fake_boto_client)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.openai_api_key == "ssm-openai-key"
    assert settings.secret_key == "ssm-secret"
    assert settings.database_url == "postgresql+psycopg://ssm-user:ssm-pass@db/app"
    assert settings.ssm_enabled is True
    assert settings.ssm_parameter_path == "/marketing-agent/prod"
    assert settings.allowed_origins == ["https://app.example.com"]
    assert settings.ssm_loaded_parameters == 5
    assert client_calls[0]["service_name"] == "ssm"
    assert client_calls[0]["region_name"] == "ap-south-1"
    assert fake_client.calls == [
        {
            "Path": "/marketing-agent/prod",
            "Recursive": True,
            "WithDecryption": True,
            "MaxResults": 10,
        },
        {
            "Path": "/marketing-agent/prod",
            "Recursive": True,
            "WithDecryption": True,
            "MaxResults": 10,
            "NextToken": "page-2",
        },
    ]
    get_settings.cache_clear()


def test_runtime_ssm_fails_startup_when_required_loading_fails(monkeypatch):
    monkeypatch.setenv("SSM_ENABLED", "true")
    monkeypatch.setenv("SSM_FAIL_FAST", "true")
    monkeypatch.setattr(
        "app.core.aws_ssm.boto3.client",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("AWS unavailable")),
    )
    get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="application startup aborted"):
        get_settings()
    get_settings.cache_clear()


def test_runtime_ssm_can_fall_back_for_local_recovery(monkeypatch):
    monkeypatch.setenv("SSM_ENABLED", "true")
    monkeypatch.setenv("SSM_FAIL_FAST", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "local-recovery-key")
    monkeypatch.setattr(
        "app.core.aws_ssm.boto3.client",
        lambda *args, **kwargs: (_ for _ in ()).throw(ConnectionError("AWS unavailable")),
    )
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.openai_api_key == "local-recovery-key"
    assert settings.ssm_enabled is True
    assert settings.ssm_loaded_parameters == 0
    get_settings.cache_clear()
