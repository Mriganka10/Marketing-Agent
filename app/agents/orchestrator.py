from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.analytics_refresh import AnalyticsRefreshAgent
from app.agents.content import ContentPageCreationAgent
from app.agents.research import ResearchAgent
from app.models.entities import BusinessProfile, Campaign


class MarketingOrchestrator:
    def __init__(
        self,
        research_agent: ResearchAgent,
        content_agent: ContentPageCreationAgent,
        analytics_agent: AnalyticsRefreshAgent,
    ) -> None:
        self.research_agent = research_agent
        self.content_agent = content_agent
        self.analytics_agent = analytics_agent

    def run(self, db: Session, campaign: Campaign, *, publish_pages: bool = True) -> dict[str, object]:
        business = db.get(BusinessProfile, campaign.business_id)
        if not business:
            raise ValueError("Campaign business profile does not exist.")
        signals = self.research_agent.generate_signals(db, campaign, business)
        pages = self.content_agent.create_pages(
            db, campaign, business, signals, publish=publish_pages
        )
        recommendations = self.analytics_agent.recommend(db, campaign)
        return {
            "campaign": campaign,
            "demand_signals": signals,
            "pages": pages,
            "recommendations": recommendations,
        }

