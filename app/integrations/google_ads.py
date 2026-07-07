from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

    def validate_campaign_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        return self._mutate_campaign_plan(plan, validate_only=True)

    def create_campaign_from_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        return self._mutate_campaign_plan(plan, validate_only=False)

    def update_campaign_controls(
        self,
        *,
        campaign_resource_name: str,
        budget_resource_name: str | None,
        name: str,
        status: str,
        daily_budget_micros: int,
        validate_only: bool = True,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise GoogleAdsError("Google Ads credentials are required.")
        if not campaign_resource_name:
            raise GoogleAdsError("A pushed Google campaign resource is required before updates can be sent.")
        operations: list[dict[str, Any]] = [
            {
                "campaignOperation": {
                    "update": {
                        "resourceName": campaign_resource_name,
                        "name": name,
                        "status": status,
                    },
                    "updateMask": "name,status",
                }
            }
        ]
        if budget_resource_name:
            operations.insert(
                0,
                {
                    "campaignBudgetOperation": {
                        "update": {
                            "resourceName": budget_resource_name,
                            "amountMicros": str(daily_budget_micros),
                        },
                        "updateMask": "amount_micros",
                    }
                },
            )
        return self._mutate(operations, validate_only=validate_only)

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

    def _mutate_campaign_plan(self, plan: dict[str, Any], *, validate_only: bool) -> dict[str, Any]:
        if not self.is_configured:
            raise GoogleAdsError("Google Ads credentials are required.")
        customer_id = self._digits(self.settings.google_ads_customer_id or "")
        budget_resource = f"customers/{customer_id}/campaignBudgets/-1"
        campaign_resource = f"customers/{customer_id}/campaigns/-2"
        ad_group_resource = f"customers/{customer_id}/adGroups/-3"
        keywords = plan.get("keywords") or []
        headlines = plan.get("headlines") or []
        descriptions = plan.get("descriptions") or []
        final_url = (plan.get("final_urls") or [self.settings.public_base_url])[0]
        campaign_status = plan.get("campaign_status") or "PAUSED"
        ad_group_status = plan.get("ad_group_status") or "PAUSED"
        operations: list[dict[str, Any]] = [
            {
                "campaignBudgetOperation": {
                    "create": {
                        "resourceName": budget_resource,
                        "name": f"{plan.get('name', 'Marketing Agent Campaign')} Budget",
                        "amountMicros": str(int(plan.get("daily_budget_micros") or 5_000_000)),
                        "deliveryMethod": "STANDARD",
                        "explicitlyShared": False,
                    }
                }
            },
            {
                "campaignOperation": {
                    "create": {
                        "resourceName": campaign_resource,
                        "name": str(plan.get("name") or "Marketing Agent Search Campaign"),
                        "status": campaign_status,
                        "advertisingChannelType": "SEARCH",
                        "campaignBudget": budget_resource,
                        "manualCpc": {},
                        "networkSettings": {
                            "targetGoogleSearch": True,
                            "targetSearchNetwork": True,
                            "targetContentNetwork": False,
                            "targetPartnerSearchNetwork": False,
                        },
                    }
                }
            },
            {
                "adGroupOperation": {
                    "create": {
                        "resourceName": ad_group_resource,
                        "name": str(plan.get("ad_group_name") or "Core demand ad group"),
                        "campaign": campaign_resource,
                        "status": ad_group_status,
                        "type": "SEARCH_STANDARD",
                        "cpcBidMicros": str(int(plan.get("cpc_bid_micros") or 1_000_000)),
                    }
                }
            },
        ]
        for index, keyword in enumerate(keywords[:12], start=4):
            operations.append(
                {
                    "adGroupCriterionOperation": {
                        "create": {
                            "resourceName": f"customers/{customer_id}/adGroupCriteria/-{index}",
                            "adGroup": ad_group_resource,
                            "status": "PAUSED",
                            "keyword": {
                                "text": str(keyword.get("text") or keyword),
                                "matchType": str(keyword.get("match_type") or "PHRASE"),
                            },
                        }
                    }
                }
            )
        operations.append(
            {
                "adGroupAdOperation": {
                    "create": {
                        "adGroup": ad_group_resource,
                        "status": "PAUSED",
                        "ad": {
                            "finalUrls": [final_url],
                            "responsiveSearchAd": {
                                "headlines": [{"text": str(item)[:30]} for item in headlines[:15]],
                                "descriptions": [{"text": str(item)[:90]} for item in descriptions[:4]],
                            },
                        },
                    }
                }
            }
        )
        return self._mutate(operations, validate_only=validate_only)

    def _mutate(self, operations: list[dict[str, Any]], *, validate_only: bool) -> dict[str, Any]:
        access_token = self._access_token()
        customer_id = self._digits(self.settings.google_ads_customer_id or "")
        login_customer_id = self._digits(
            self.settings.google_ads_login_customer_id or self.settings.google_ads_customer_id or ""
        )
        url = (
            f"https://googleads.googleapis.com/{self.settings.google_ads_api_version}"
            f"/customers/{customer_id}/googleAds:mutate"
        )
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "developer-token": self.settings.google_ads_developer_token or "",
                    "login-customer-id": login_customer_id,
                },
                json={"mutateOperations": operations, "partialFailure": False, "validateOnly": validate_only},
                timeout=30,
            )
            payload = response.json()
            response.raise_for_status()
        except Exception as exc:
            detail = payload if "payload" in locals() else str(exc)
            raise GoogleAdsError(f"Google Ads mutate failed: {detail}") from exc
        return {
            "validate_only": validate_only,
            "operation_count": len(operations),
            "response": payload,
        }

    @staticmethod
    def _digits(value: str) -> str:
        return "".join(ch for ch in value if ch.isdigit())
