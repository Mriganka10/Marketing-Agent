from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.models.entities import BusinessProfile, Campaign
from app.models.schemas import BusinessProfileCreate, CampaignCreate


class BusinessMemoryAgent:
    name = "business_memory_agent"

    def upsert_business(self, db: Session, payload: BusinessProfileCreate) -> BusinessProfile:
        business = BusinessProfile(
            name=payload.name,
            website=str(payload.website) if payload.website else None,
            industry=payload.industry,
            audience=payload.audience,
            value_proposition=payload.value_proposition,
            offers=payload.offers,
            competitors=payload.competitors,
            tone=payload.tone,
        )
        db.add(business)
        db.commit()
        db.refresh(business)
        record_audit(
            db,
            actor=self.name,
            action="business_profile_created",
            entity_type="business_profile",
            entity_id=business.id,
            metadata={"industry": business.industry, "offers": business.offers},
        )
        return business

    def create_campaign(self, db: Session, payload: CampaignCreate) -> Campaign:
        campaign = Campaign(
            business_id=payload.business_id,
            name=payload.name,
            goal=payload.goal,
            target_region=payload.target_region,
            status="ready",
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        record_audit(
            db,
            actor=self.name,
            action="campaign_created",
            entity_type="campaign",
            entity_id=campaign.id,
            metadata={"goal": campaign.goal, "target_region": campaign.target_region},
        )
        return campaign

