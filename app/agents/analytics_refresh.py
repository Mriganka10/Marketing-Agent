from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import Settings, get_settings
from app.agents.seo_analytics import SeoAnalyticsAgent
from app.models.entities import Campaign, LandingPage, RefreshRecommendation


class AnalyticsRefreshAgent:
    name = "analytics_refresh_agent"

    def recommend(
        self, db: Session, campaign: Campaign, settings: Settings | None = None
    ) -> list[RefreshRecommendation]:
        settings = settings or get_settings()
        seo_agent = SeoAnalyticsAgent()
        pages = db.query(LandingPage).filter(LandingPage.campaign_id == campaign.id).all()
        recommendations: list[RefreshRecommendation] = []
        for page in pages:
            score = seo_agent.score_page(db, page, settings)
            if score.impressions < 100:
                recommendation = RefreshRecommendation(
                    campaign_id=campaign.id,
                    page_id=page.id,
                    severity="low",
                    recommendation=(
                        f"Improve discovery for '{page.title}' with stronger keyword targeting, "
                        "internal links, sitemap coverage, and richer section depth."
                    ),
                    expected_impact="More Google impressions and enough traffic for reliable conversion analysis.",
                )
            elif score.impressions >= 300 and score.ctr < 2:
                recommendation = RefreshRecommendation(
                    campaign_id=campaign.id,
                    page_id=page.id,
                    severity="high",
                    recommendation=(
                        f"Rewrite the SEO title, meta description, and schema for '{page.title}' "
                        "because impressions are healthy but CTR is weak."
                    ),
                    expected_impact="Higher organic click-through rate from existing search visibility.",
                )
            elif score.sessions >= 25 and score.conversion_rate < 3:
                recommendation = RefreshRecommendation(
                    campaign_id=campaign.id,
                    page_id=page.id,
                    severity="high",
                    recommendation=(
                        f"Refresh the hero, proof, CTA, and lead form for '{page.title}' "
                        "because visitors are arriving but not converting."
                    ),
                    expected_impact="Higher form-start and form-submit rates from organic traffic.",
                )
            else:
                recommendation = RefreshRecommendation(
                    campaign_id=campaign.id,
                    page_id=page.id,
                    severity="medium",
                    recommendation=(
                        f"Scale '{page.title}' into adjacent keyword, geography, persona, or industry variants."
                    ),
                    expected_impact="Incremental qualified traffic and leads from a proven page pattern.",
                )
            db.add(recommendation)
            recommendations.append(recommendation)
        seo_agent.record_recommendation_run(
            db, campaign, pages=len(pages), recommendations=len(recommendations)
        )
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
