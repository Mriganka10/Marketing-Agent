from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.agents.llm import LLMService
from app.core.audit import record_audit
from app.core.content_formatting import coerce_text, normalize_sections, normalize_seo
from app.models.entities import BusinessProfile, Campaign, DemandSignal, LandingPage


class ContentPageCreationAgent:
    name = "content_page_creation_agent"

    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def create_pages(
        self,
        db: Session,
        campaign: Campaign,
        business: BusinessProfile,
        signals: list[DemandSignal],
        *,
        publish: bool,
    ) -> list[LandingPage]:
        pages: list[LandingPage] = []
        for signal in signals[:4]:
            fallback = self._fallback_page(business, campaign, signal)
            payload = self.llm.json_completion(
                system=(
                    "You create conversion-focused landing page JSON. Return keys: title, hero, "
                    "sections as array of {heading, body}, cta, seo with description and keywords."
                ),
                user=(
                    f"Business: {business.name}\nAudience: {business.audience}\nTone: {business.tone}\n"
                    f"Value proposition: {business.value_proposition}\nCampaign goal: {campaign.goal}\n"
                    f"Keyword: {signal.keyword}\nIntent: {signal.intent}"
                ),
                fallback=fallback,
            )
            page = LandingPage(
                campaign_id=campaign.id,
                slug=self._unique_slug(db, f"{business.name}-{signal.keyword}"),
                title=coerce_text(payload.get("title"), str(fallback["title"]))[:220],
                hero=coerce_text(payload.get("hero"), str(fallback["hero"])),
                sections=normalize_sections(payload.get("sections"), fallback["sections"]),
                cta=coerce_text(payload.get("cta"), str(fallback["cta"]))[:160],
                seo=normalize_seo(payload.get("seo"), fallback["seo"]),
                status="published" if publish else "draft",
            )
            db.add(page)
            pages.append(page)
        campaign.status = "active" if publish else "draft"
        db.commit()
        for page in pages:
            db.refresh(page)
        record_audit(
            db,
            actor=self.name,
            action="landing_pages_created",
            entity_type="campaign",
            entity_id=campaign.id,
            metadata={"count": len(pages), "published": publish},
        )
        return pages

    def _fallback_page(
        self, business: BusinessProfile, campaign: Campaign, signal: DemandSignal
    ) -> dict[str, object]:
        return {
            "title": f"{business.name} for {signal.keyword.title()}",
            "hero": (
                f"Turn {campaign.goal.lower()} into a repeatable growth channel with "
                f"{business.name}'s {business.industry} expertise."
            ),
            "sections": [
                {
                    "heading": "Built around your buyer intent",
                    "body": (
                        f"This page targets '{signal.keyword}' and speaks directly to "
                        f"{business.audience} with a clear path from interest to inquiry."
                    ),
                },
                {
                    "heading": "Why it is credible",
                    "body": business.value_proposition,
                },
                {
                    "heading": "What happens next",
                    "body": "Qualified prospects can share their context and move into a focused sales conversation.",
                },
            ],
            "cta": "Request a growth consultation",
            "seo": {
                "description": f"{business.name} helps {business.audience} with {campaign.goal}.",
                "keywords": [signal.keyword, business.industry, campaign.target_region],
            },
        }

    def _unique_slug(self, db: Session, value: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:130] or "landing-page"
        slug = base
        index = 2
        while db.query(LandingPage).filter(LandingPage.slug == slug).first():
            slug = f"{base}-{index}"
            index += 1
        return slug
