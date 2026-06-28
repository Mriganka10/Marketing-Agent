from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.llm import LLMService
from app.core.audit import record_audit
from app.models.entities import BusinessProfile, Campaign, DemandSignal


class ResearchAgent:
    name = "research_agent"

    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    def generate_signals(self, db: Session, campaign: Campaign, business: BusinessProfile) -> list[DemandSignal]:
        fallback_keywords = self._fallback_signals(campaign, business)
        payload = self.llm.json_completion(
            system=(
                "You are a senior B2B growth strategist. Return JSON with a 'signals' array. "
                "Each item must include keyword, intent, priority_score between 0 and 100, and rationale."
            ),
            user=(
                f"Business: {business.name}\nIndustry: {business.industry}\nAudience: {business.audience}\n"
                f"Value proposition: {business.value_proposition}\nOffers: {business.offers}\n"
                f"Campaign goal: {campaign.goal}\nRegion: {campaign.target_region}"
            ),
            fallback={"signals": fallback_keywords},
        )
        signals = payload.get("signals") if isinstance(payload.get("signals"), list) else fallback_keywords
        created: list[DemandSignal] = []
        for item in signals[:8]:
            signal = DemandSignal(
                campaign_id=campaign.id,
                keyword=str(item.get("keyword", business.industry))[:180],
                intent=str(item.get("intent", "commercial"))[:80],
                region=campaign.target_region,
                priority_score=float(item.get("priority_score", 70)),
                rationale=str(item.get("rationale", "Relevant to campaign demand.")),
            )
            db.add(signal)
            created.append(signal)
        db.commit()
        for signal in created:
            db.refresh(signal)
        record_audit(
            db,
            actor=self.name,
            action="demand_signals_generated",
            entity_type="campaign",
            entity_id=campaign.id,
            metadata={"count": len(created)},
        )
        return created

    def _fallback_signals(self, campaign: Campaign, business: BusinessProfile) -> list[dict[str, object]]:
        core = business.industry.lower()
        offer = business.offers[0] if business.offers else business.value_proposition.split(".")[0]
        return [
            {
                "keyword": f"{core} services for {business.audience[:48]}",
                "intent": "solution-aware",
                "priority_score": 88,
                "rationale": "Maps the core offer to the stated buyer audience.",
            },
            {
                "keyword": f"best {core} partner {campaign.target_region}",
                "intent": "vendor-comparison",
                "priority_score": 82,
                "rationale": "Targets buyers comparing options in the target region.",
            },
            {
                "keyword": f"{offer} implementation",
                "intent": "high-intent",
                "priority_score": 79,
                "rationale": "Captures buyers looking for implementation help.",
            },
            {
                "keyword": f"how to improve {campaign.goal[:64].lower()}",
                "intent": "educational",
                "priority_score": 72,
                "rationale": "Supports top-of-funnel content tied to campaign goals.",
            },
        ]

