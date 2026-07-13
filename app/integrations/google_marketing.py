from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.core.config import Settings


GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


class GoogleMarketingIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchConsoleRow:
    date: date
    page_url: str
    query: str
    country: str
    device: str
    clicks: int
    impressions: int
    ctr: float
    position: float


@dataclass(frozen=True)
class GA4PageRow:
    date: date
    path: str
    sessions: int
    engaged_sessions: int
    traffic_source: str
    device: str
    country: str


@dataclass(frozen=True)
class GA4EventRow:
    date: date
    path: str
    event_name: str
    event_count: int


@dataclass(frozen=True)
class GoogleMarketingData:
    start_date: date
    end_date: date
    search_rows: list[SearchConsoleRow]
    search_query_rows: list[SearchConsoleRow]
    analytics_rows: list[GA4PageRow]
    analytics_event_rows: list[GA4EventRow]


class GoogleMarketingIntegration:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.google_service_account_json
            and self.settings.ga4_property_id
            and self.settings.google_search_console_site_url
        )

    def fetch(self, *, days: int = 28, row_limit: int = 25000) -> GoogleMarketingData:
        if not self.is_configured:
            raise GoogleMarketingIntegrationError("GA4, Search Console, and service account credentials are required.")

        end_date = date.today() - timedelta(days=2)
        start_date = end_date - timedelta(days=days - 1)
        credentials = self._credentials()
        return GoogleMarketingData(
            start_date=start_date,
            end_date=end_date,
            search_rows=self._fetch_search_console_pages(credentials, start_date, end_date, row_limit),
            search_query_rows=self._fetch_search_console_queries(credentials, start_date, end_date, row_limit),
            analytics_rows=self._fetch_ga4_pages(credentials, start_date, end_date, row_limit),
            analytics_event_rows=self._fetch_ga4_events(credentials, start_date, end_date, row_limit),
        )

    def _credentials(self) -> Any:
        try:
            from google.oauth2 import service_account
        except Exception as exc:  # pragma: no cover - dependency issue is surfaced at runtime
            raise GoogleMarketingIntegrationError("Google auth dependencies are not installed.") from exc

        try:
            service_account_info = json.loads(self.settings.google_service_account_json or "{}")
            return service_account.Credentials.from_service_account_info(
                service_account_info,
                scopes=[GSC_SCOPE, GA4_SCOPE],
            )
        except Exception as exc:
            raise GoogleMarketingIntegrationError("Google service account JSON is invalid.") from exc

    def _fetch_search_console_pages(
        self,
        credentials: Any,
        start_date: date,
        end_date: date,
        row_limit: int,
    ) -> list[SearchConsoleRow]:
        try:
            from googleapiclient.discovery import build
        except Exception as exc:  # pragma: no cover
            raise GoogleMarketingIntegrationError("Google API client dependencies are not installed.") from exc

        try:
            service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
            response = (
                service.searchanalytics()
                .query(
                    siteUrl=self.settings.google_search_console_site_url,
                    body={
                        "startDate": start_date.isoformat(),
                        "endDate": end_date.isoformat(),
                        "dimensions": ["date", "page"],
                        "rowLimit": row_limit,
                        "startRow": 0,
                    },
                )
                .execute()
            )
        except Exception as exc:
            raise GoogleMarketingIntegrationError(f"Search Console sync failed: {exc}") from exc

        rows: list[SearchConsoleRow] = []
        for item in response.get("rows", []):
            keys = item.get("keys", [])
            if len(keys) < 2:
                continue
            rows.append(
                SearchConsoleRow(
                    date=date.fromisoformat(str(keys[0])),
                    page_url=str(keys[1]),
                    query="",
                    country="ALL",
                    device="ALL",
                    clicks=int(item.get("clicks") or 0),
                    impressions=int(item.get("impressions") or 0),
                    ctr=float(item.get("ctr") or 0),
                    position=float(item.get("position") or 0),
                )
            )
        return rows

    def _fetch_search_console_queries(
        self,
        credentials: Any,
        start_date: date,
        end_date: date,
        row_limit: int,
    ) -> list[SearchConsoleRow]:
        try:
            from googleapiclient.discovery import build
            service = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)
            response = service.searchanalytics().query(
                siteUrl=self.settings.google_search_console_site_url,
                body={
                    "startDate": start_date.isoformat(),
                    "endDate": end_date.isoformat(),
                    "dimensions": ["page", "query"],
                    "rowLimit": row_limit,
                    "startRow": 0,
                },
            ).execute()
        except Exception as exc:
            raise GoogleMarketingIntegrationError(f"Search Console query-detail sync failed: {exc}") from exc
        rows: list[SearchConsoleRow] = []
        for item in response.get("rows", []):
            keys = item.get("keys", [])
            if len(keys) < 2:
                continue
            rows.append(SearchConsoleRow(
                date=end_date,
                page_url=str(keys[0]),
                query=str(keys[1]),
                country="ALL",
                device="ALL",
                clicks=int(item.get("clicks") or 0),
                impressions=int(item.get("impressions") or 0),
                ctr=float(item.get("ctr") or 0),
                position=float(item.get("position") or 0),
            ))
        return rows

    def _fetch_ga4_pages(
        self,
        credentials: Any,
        start_date: date,
        end_date: date,
        row_limit: int,
    ) -> list[GA4PageRow]:
        try:
            from googleapiclient.discovery import build
        except Exception as exc:  # pragma: no cover
            raise GoogleMarketingIntegrationError("Google API client dependencies are not installed.") from exc

        try:
            service = build("analyticsdata", "v1beta", credentials=credentials, cache_discovery=False)
            response = (
                service.properties()
                .runReport(
                    property=f"properties/{self.settings.ga4_property_id}",
                    body={
                        "dateRanges": [
                            {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
                        ],
                        "dimensions": [
                            {"name": "date"},
                            {"name": "pagePath"},
                            {"name": "sessionDefaultChannelGroup"},
                            {"name": "deviceCategory"},
                            {"name": "country"},
                        ],
                        "metrics": [
                            {"name": "sessions"},
                            {"name": "engagedSessions"},
                        ],
                        "limit": row_limit,
                    },
                )
                .execute()
            )
        except Exception as exc:
            raise GoogleMarketingIntegrationError(f"GA4 sync failed: {exc}") from exc

        rows: list[GA4PageRow] = []
        for item in response.get("rows", []):
            dimensions = [value.get("value", "") for value in item.get("dimensionValues", [])]
            metrics = [value.get("value", "0") for value in item.get("metricValues", [])]
            if len(dimensions) < 5 or len(metrics) < 2:
                continue
            rows.append(
                GA4PageRow(
                    date=self._ga4_date(dimensions[0]),
                    path=str(dimensions[1]) or "/",
                    traffic_source=str(dimensions[2]) or "unknown",
                    device=str(dimensions[3]).upper() or "ALL",
                    country=str(dimensions[4]).upper() or "ALL",
                    sessions=int(float(metrics[0] or 0)),
                    engaged_sessions=int(float(metrics[1] or 0)),
                )
            )
        return rows

    def _fetch_ga4_events(
        self,
        credentials: Any,
        start_date: date,
        end_date: date,
        row_limit: int,
    ) -> list[GA4EventRow]:
        try:
            from googleapiclient.discovery import build
            service = build("analyticsdata", "v1beta", credentials=credentials, cache_discovery=False)
            response = service.properties().runReport(
                property=f"properties/{self.settings.ga4_property_id}",
                body={
                    "dateRanges": [{"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}],
                    "dimensions": [{"name": "date"}, {"name": "pagePath"}, {"name": "eventName"}],
                    "metrics": [{"name": "eventCount"}],
                    "limit": row_limit,
                },
            ).execute()
        except Exception as exc:
            raise GoogleMarketingIntegrationError(f"GA4 event sync failed: {exc}") from exc
        rows: list[GA4EventRow] = []
        for item in response.get("rows", []):
            dimensions = [value.get("value", "") for value in item.get("dimensionValues", [])]
            metrics = [value.get("value", "0") for value in item.get("metricValues", [])]
            if len(dimensions) < 3 or not metrics:
                continue
            rows.append(GA4EventRow(
                date=self._ga4_date(dimensions[0]),
                path=str(dimensions[1]) or "/",
                event_name=str(dimensions[2]) or "unknown",
                event_count=int(float(metrics[0] or 0)),
            ))
        return rows

    @staticmethod
    def _ga4_date(value: str) -> date:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
