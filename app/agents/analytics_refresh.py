from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.models.entities import Campaign, LandingPage, RefreshRecommendation


class AnalyticsRefreshAgent:
    name = "analytics_refresh_agent"

    def recommend(self, db: Session, campaign: Campaign) -> list[RefreshRecommendation]:
        pages = db.query(LandingPage).filter(LandingPage.campaign_id == campaign.id).all()
        recommendations: list[RefreshRecommendation] = []
        for page in pages:
            rate = page.conversions / page.visits if page.visits else 0
            if page.visits < 25:
                recommendation = RefreshRecommendation(
                    campaign_id=campaign.id,
                    page_id=page.id,
                    severity="low",
                    recommendation=f"Send more qualified traffic to '{page.title}' before making major copy changes.",
                    expected_impact="More reliable conversion signal for the next refresh cycle.",
                )
            elif rate < 0.03:
                recommendation = RefreshRecommendation(
                    campaign_id=campaign.id,
                    page_id=page.id,
                    severity="high",
                    recommendation=f"Rewrite the hero and CTA for '{page.title}' around a more urgent buyer pain.",
                    expected_impact="Higher form-start rate and clearer message-market fit.",
                )
            else:
                recommendation = RefreshRecommendation(
                    campaign_id=campaign.id,
                    page_id=page.id,
                    severity="medium",
                    recommendation=f"Create a variant of '{page.title}' for the strongest converting segment.",
                    expected_impact="Incremental lift from targeted follow-up content.",
                )
            db.add(recommendation)
            recommendations.append(recommendation)
        db.commit()
        for recommendation in recommendations:
            db.refresh(recommendation)
        record_audit(
            db,
            actor=self.name,
            action="refresh_recommendations_created",
            entity_type="campaign",
            entity_id=campaign.id,
            metadata={"count": len(recommendations)},
        )
        return recommendations

