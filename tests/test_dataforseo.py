from __future__ import annotations

import httpx

from app.core.config import Settings
from app.integrations.dataforseo import DataForSEOClient


class DummyResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("POST", "https://api.dataforseo.com"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self.payload


def test_backlink_summary_uses_live_dataforseo_endpoint(monkeypatch):
    calls: list[dict] = []

    def fake_post(url, auth, json, timeout):
        calls.append({"url": url, "auth": auth, "json": json, "timeout": timeout})
        return DummyResponse(
            {
                "tasks": [
                    {
                        "result": [
                            {
                                "target": "selected-company.test",
                                "rank": 537,
                                "backlinks": 1234,
                                "referring_domains": 98,
                                "backlinks_spam_score": 2.5,
                            }
                        ]
                    }
                ]
            }
        )

    monkeypatch.setattr("app.integrations.dataforseo.httpx.post", fake_post)

    settings = Settings(dataforseo_enabled=True, dataforseo_login="api-login", dataforseo_password="api-password")
    summary = DataForSEOClient(settings).backlink_summary("https://selected-company.test", [])

    assert calls[0]["url"].endswith("/backlinks/summary/live")
    assert calls[0]["auth"] == ("api-login", "api-password")
    assert calls[0]["json"][0]["target"] == "selected-company.test"
    assert summary.source == "Live DataForSEO"
    assert summary.mode == "live_dataforseo_backlinks"
    assert summary.backlinks == 1234
    assert summary.referring_domains == 98
    assert summary.authority_score == 53.7
    assert summary.spam_score == 2.5


def test_backlink_summary_falls_back_when_dataforseo_rejects_request(monkeypatch):
    def fake_post(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "401 unauthorized",
            request=httpx.Request("POST", "https://api.dataforseo.com/v3/backlinks/summary/live"),
            response=httpx.Response(401),
        )

    def fake_get(*args, **kwargs):
        return DummyResponse({"tasks": [{"result": {"login": "hidden@example.com", "money": {"total": 1}}}]})

    monkeypatch.setattr("app.integrations.dataforseo.httpx.post", fake_post)
    monkeypatch.setattr("app.integrations.dataforseo.httpx.get", fake_get)

    settings = Settings(dataforseo_enabled=True, dataforseo_login="api-login", dataforseo_password="api-password")
    summary = DataForSEOClient(settings).backlink_summary("https://selected-company.test", [])

    assert summary.source == "Demo fallback"
    assert summary.mode == "dataforseo_backlinks_error_fallback"
    assert summary.error is not None
    assert summary.backlinks > 0


def test_backlink_summary_requires_selected_company_domain():
    summary = DataForSEOClient(Settings()).backlink_summary(None, ["competitor.test"])

    assert summary.domain == "Not configured"
    assert summary.backlinks == 0
    assert summary.source == "Configuration"
    assert summary.mode == "company_domain_required"


def test_account_status_does_not_expose_dataforseo_login(monkeypatch):
    def fake_get(*args, **kwargs):
        return DummyResponse(
            {
                "tasks": [
                    {
                        "result": {
                            "login": "owner@example.com",
                            "password": "never-return-this",
                            "money": {"total": 1},
                            "rates": {"backlinks": {}, "serp": {}},
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("app.integrations.dataforseo.httpx.get", fake_get)

    settings = Settings(dataforseo_enabled=True, dataforseo_login="api-login", dataforseo_password="api-password")
    status = DataForSEOClient(settings).account_status()

    assert status["mode"] == "live_dataforseo_ready"
    assert status["account"]["login_configured"] is True
    assert "owner@example.com" not in str(status)
    assert "never-return-this" not in str(status)
