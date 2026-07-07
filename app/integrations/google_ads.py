from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import Settings


class GoogleAdsError(RuntimeError):
    pass


@dataclass(frozen=True)
class GoogleAdsCampaign:
    campaign_id: str
    name: str
    status: str
    impressions: int
    clicks: int
    cost_micros: int
    conversions: float


class GoogleAdsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return self.settings.can_use_google_ads

    def readiness(self) -> dict[str, object]:
        return {
            "configured": self.is_configured,
            "developer_token": bool(self.settings.google_ads_developer_token),
            "oauth_client": bool(self.settings.google_ads_client_id and self.settings.google_ads_client_secret),
            "refresh_token": bool(self.settings.google_ads_refresh_token),
            "customer_id": bool(self.settings.google_ads_customer_id),
            "login_customer_id": bool(self.settings.google_ads_login_customer_id),
            "api_version": self.settings.google_ads_api_version,
            "mode": "google_ads_live_ready" if self.is_configured else "ready_for_google_ads_credentials",
        }

    def fetch_campaigns(self) -> list[GoogleAdsCampaign]:
        if not self.is_configured:
            raise GoogleAdsError("Google Ads credentials are required.")
        access_token = self._access_token()
        customer_id = self._digits(self.settings.google_ads_customer_id or "")
        login_customer_id = self._digits(
            self.settings.google_ads_login_customer_id or self.settings.google_ads_customer_id or ""
        )
        url = (
            f"https://googleads.googleapis.com/{self.settings.google_ads_api_version}"
            f"/customers/{customer_id}/googleAds:searchStream"
        )
        query = """
            SELECT
              campaign.id,
              campaign.name,
              campaign.status,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions
            FROM campaign
            WHERE segments.date DURING LAST_30_DAYS
            LIMIT 20
        """
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "developer-token": self.settings.google_ads_developer_token or "",
                    "login-customer-id": login_customer_id,
                },
                json={"query": " ".join(query.split())},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise GoogleAdsError(f"Google Ads campaign sync failed: {exc}") from exc

        campaigns: list[GoogleAdsCampaign] = []
        for batch in payload if isinstance(payload, list) else []:
            for row in batch.get("results", []):
                campaign = row.get("campaign", {})
                metrics = row.get("metrics", {})
                campaigns.append(
                    GoogleAdsCampaign(
                        campaign_id=str(campaign.get("id") or ""),
                        name=str(campaign.get("name") or "Unnamed campaign"),
                        status=str(campaign.get("status") or "UNKNOWN"),
                        impressions=int(metrics.get("impressions") or 0),
                        clicks=int(metrics.get("clicks") or 0),
                        cost_micros=int(metrics.get("costMicros") or 0),
                        conversions=float(metrics.get("conversions") or 0),
                    )
                )
        return campaigns

    def _access_token(self) -> str:
        try:
            response = httpx.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.settings.google_ads_client_id,
                    "client_secret": self.settings.google_ads_client_secret,
                    "refresh_token": self.settings.google_ads_refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=20,
            )
            response.raise_for_status()
            access_token = response.json().get("access_token")
        except Exception as exc:
            raise GoogleAdsError(f"Google Ads OAuth refresh failed: {exc}") from exc
        if not access_token:
            raise GoogleAdsError("Google Ads OAuth response did not include an access token.")
        return str(access_token)

    @staticmethod
    def _digits(value: str) -> str:
        return "".join(ch for ch in value if ch.isdigit())
