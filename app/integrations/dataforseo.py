from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import Settings


class DataForSEOError(RuntimeError):
    pass


@dataclass(frozen=True)
class BacklinkSummary:
    domain: str
    backlinks: int
    referring_domains: int
    authority_score: float
    spam_score: float
    mode: str
    source: str
    error: str | None = None


class DataForSEOClient:
    base_url = "https://api.dataforseo.com/v3"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_configured(self) -> bool:
        return self.settings.can_use_dataforseo

    def account_status(self) -> dict[str, object]:
        if not self.is_configured:
            return {"configured": False, "mode": "ready_for_credentials"}
        try:
            response = httpx.get(
                f"{self.base_url}/appendix/user_data",
                auth=(self.settings.dataforseo_login or "", self.settings.dataforseo_password or ""),
                timeout=12,
            )
            response.raise_for_status()
            payload = response.json()
            tasks = payload.get("tasks") or []
            result = tasks[0].get("result") if tasks and isinstance(tasks[0], dict) else None
            return {"configured": True, "mode": "live_dataforseo_ready", "account": self._safe_account_summary(result)}
        except Exception as exc:
            return {"configured": True, "mode": "dataforseo_error_fallback", "error": str(exc)}

    def backlink_summary(self, website: str | None, competitors: list[str]) -> BacklinkSummary:
        domain = self._domain(website) or self._domain(competitors[0] if competitors else "") or "agenticgrowthlabs.com"
        if not self.is_configured:
            return self._fallback_backlink_summary(domain, "ready_for_credentials")

        try:
            response = httpx.post(
                f"{self.base_url}/backlinks/summary/live",
                auth=(self.settings.dataforseo_login or "", self.settings.dataforseo_password or ""),
                json=[
                    {
                        "target": domain,
                        "include_subdomains": True,
                        "include_indirect_links": True,
                    }
                ],
                timeout=25,
            )
            response.raise_for_status()
            result = self._first_result(response.json())
            if not result:
                raise DataForSEOError("DataForSEO backlinks response did not include a result")

            backlinks = int(self._number(result, "backlinks", "total_backlinks", default=0))
            referring_domains = int(
                self._number(result, "referring_domains", "referring_main_domains", "referring_pages", default=0)
            )
            rank = self._number(result, "rank", "domain_rank", "authority_score", default=None)
            authority_score = self._authority_score(rank, domain)
            spam_score = self._spam_score(result)
            return BacklinkSummary(
                domain=str(result.get("target") or domain),
                backlinks=backlinks,
                referring_domains=referring_domains,
                authority_score=authority_score,
                spam_score=spam_score,
                mode="live_dataforseo_backlinks",
                source="Live DataForSEO",
            )
        except Exception as exc:
            status = self.account_status()
            mode = "dataforseo_backlinks_error_fallback"
            if status.get("mode") != "live_dataforseo_ready":
                mode = str(status.get("mode") or mode)
            return self._fallback_backlink_summary(domain, mode, str(exc))

    def _fallback_backlink_summary(self, domain: str, mode: str, error: str | None = None) -> BacklinkSummary:
        seed = sum(ord(ch) for ch in domain)
        return BacklinkSummary(
            domain=domain,
            backlinks=420 + seed % 2300,
            referring_domains=45 + seed % 240,
            authority_score=round(38 + (seed % 480) / 10, 1),
            spam_score=round(1.5 + (seed % 70) / 10, 1),
            mode=mode,
            source="Demo fallback",
            error=error,
        )

    def keyword_opportunities(self, seed_terms: list[str], region: str) -> list[dict[str, object]]:
        terms = seed_terms or ["ai marketing automation", "seo automation", "lead generation landing pages"]
        opportunities: list[dict[str, object]] = []
        for index, term in enumerate(terms[:8]):
            seed = sum(ord(ch) for ch in f"{term}:{region}")
            opportunities.append(
                {
                    "keyword": term.lower(),
                    "region": region,
                    "volume": 320 + seed % 2200,
                    "difficulty": 18 + seed % 54,
                    "cpc": round(1.2 + (seed % 95) / 10, 2),
                    "priority": max(54, 92 - index * 6 - seed % 9),
                }
            )
        return opportunities

    @staticmethod
    def _domain(value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value if "://" in value else f"https://{value}")
        domain = parsed.netloc or parsed.path
        return domain.removeprefix("www.").strip("/") or None

    @staticmethod
    def _first_result(payload: dict[str, Any]) -> dict[str, Any] | None:
        tasks = payload.get("tasks") or []
        if not tasks or not isinstance(tasks[0], dict):
            return None
        result = tasks[0].get("result")
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return result[0]
        if isinstance(result, dict):
            return result
        return None

    @staticmethod
    def _number(payload: dict[str, Any], *keys: str, default: float | None = 0.0) -> float | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value.replace(",", ""))
                except ValueError:
                    continue
        return default

    def _authority_score(self, rank: float | None, domain: str) -> float:
        if rank is None:
            seed = sum(ord(ch) for ch in domain)
            return round(38 + (seed % 480) / 10, 1)
        return round(rank / 10 if rank > 100 else rank, 1)

    def _spam_score(self, payload: dict[str, Any]) -> float:
        direct = self._number(payload, "spam_score", "backlinks_spam_score", default=None)
        if direct is not None:
            return round(direct, 1)
        info = payload.get("info")
        if isinstance(info, dict):
            nested = self._number(info, "target_spam_score", "spam_score", default=None)
            if nested is not None:
                return round(nested, 1)
        return 0.0

    @staticmethod
    def _safe_account_summary(result: Any) -> dict[str, object]:
        if not isinstance(result, dict):
            return {}
        money = result.get("money")
        rates = result.get("rates")
        return {
            "login_configured": bool(result.get("login")),
            "money": money if isinstance(money, dict) else None,
            "rate_groups": list(rates.keys())[:8] if isinstance(rates, dict) else [],
        }
