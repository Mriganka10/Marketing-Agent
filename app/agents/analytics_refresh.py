from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import Settings, get_settings
from app.agents.auto_refresh_approval import AutoRefreshApprovalAgent
from app.agents.llm import LLMService
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
            if score.overall_score >= 70:
                continue
            existing = (
                db.query(RefreshRecommendation)
                .filter(
                    RefreshRecommendation.campaign_id == campaign.id,
                    RefreshRecommendation.page_id == page.id,
                    RefreshRecommendation.status.in_(["open", "pending_approval", "approved"]),
                )
                .order_by(RefreshRecommendation.created_at.desc())
                .first()
            )
            if existing:
                recommendations.append(existing)
                continue
            if score.impressions < 100:
                diagnosis = "Search discovery is below the minimum signal threshold."
                exact_action = "Rewrite the SEO title and description, add one keyword-focused section, and add two internal links."
                target = "Reach at least 100 search impressions before the next review."
            elif score.impressions >= 300 and score.ctr < 2:
                diagnosis = "The page has search visibility, but its result is not earning enough clicks."
                exact_action = "Replace the SEO title and meta description with the queued benefit-led copy and align the hero promise."
                target = "Increase organic click-through rate to at least 2%."
            elif score.sessions >= 25 and score.conversion_rate < 3:
                diagnosis = "The page receives traffic, but too few visitors complete the conversion path."
                exact_action = "Replace the hero and CTA with the queued copy and add a proof-and-next-steps section above the form."
                target = "Increase the landing-page conversion rate to at least 3%."
            else:
                diagnosis = score.diagnosis
                exact_action = score.next_action
                target = "Raise the composite SEO and conversion score to at least 70/100."
            recommendation = RefreshRecommendation(
                campaign_id=campaign.id,
                page_id=page.id,
                severity="critical" if score.overall_score < 55 else "high",
                recommendation=(
                    f"Low-performing page '{page.title}' scored {score.overall_score}/100. "
                    f"Diagnosis: {diagnosis} Queued change: {exact_action}"
                ),
                expected_impact=target,
            )
            db.add(recommendation)
            db.flush()
            AutoRefreshApprovalAgent(LLMService(settings)).draft_rewrite(
                db,
                recommendation,
                performance={
                    "overall_score": score.overall_score,
                    "threshold": 70,
                    "diagnosis": diagnosis,
                    "next_action": exact_action,
                    "impressions": score.impressions,
                    "ctr": score.ctr,
                    "sessions": score.sessions,
                    "conversion_rate": score.conversion_rate,
                    "metric_sources": score.metric_sources,
                },
                commit=False,
            )
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
            metadata={"count": len(recommendations), "rewrite_drafts": len(recommendations)},
        )
        return recommendations
