from __future__ import annotations

from statistics import mean
from urllib.parse import urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.llm import LLMService
from app.agents.seo_analytics import SeoAnalyticsAgent
from app.core.audit import record_audit
from app.core.config import Settings
from app.integrations.dataforseo import DataForSEOClient
from app.integrations.google_ads import GoogleAdsClient, GoogleAdsError
from app.models.entities import (
    BusinessProfile,
    Campaign,
    GrowthAgentExecution,
    LandingPage,
    Lead,
    PaidAdPlan,
    RefreshApprovalPlan,
    RefreshRecommendation,
)
from app.models.schemas import GrowthAgentCard, GrowthSuiteOverview


class GrowthSuiteAgent:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm
        self.seo_agent = SeoAnalyticsAgent()

    def overview(
        self,
        db: Session,
        settings: Settings,
        *,
        persist: bool = False,
        business_id: str | None = None,
    ) -> GrowthSuiteOverview:
        businesses = db.query(BusinessProfile).order_by(BusinessProfile.created_at.desc()).all()
        campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
        pages = db.query(LandingPage).order_by(LandingPage.created_at.desc()).all()
        leads = db.query(Lead).order_by(Lead.created_at.desc()).all()
        selected_business = self._select_business(businesses, business_id)
        seo = self.seo_agent.overview(db, settings)
        dataforseo = DataForSEOClient(settings)
        google_ads = GoogleAdsClient(settings)

        agents = [
            self._ai_search_visibility(businesses, pages, settings),
            self._backlink_authority(selected_business, campaigns, dataforseo),
            self._auto_refresh_approval(db, campaigns, seo),
            self._paid_campaigns(db, campaigns, google_ads),
            self._client_reporting(businesses, campaigns, pages, leads, seo),
            self._workspace_access(businesses, campaigns, pages, leads),
        ]

        if persist:
            for agent in agents:
                self._persist_execution(db, agent)
            record_audit(
                db,
                actor="growth_suite_agent",
                action="growth_suite_synced",
                entity_type="growth_agents",
                metadata={"agents": [agent.key for agent in agents]},
            )
            db.commit()

        return GrowthSuiteOverview(
            mode=self._suite_mode(settings, dataforseo, google_ads),
            readiness={
                "openai": {
                    "configured": settings.can_use_openai,
                    "model": settings.openai_model,
                    "scope": "ChatGPT/OpenAI visibility only",
                },
                "dataforseo": dataforseo.account_status(),
                "google_ads": google_ads.readiness(),
                "seo": seo.integration_status,
            },
            selected_business=self._selected_business_payload(selected_business),
            agents=agents,
            client_workspaces=self._client_workspaces(businesses, campaigns, pages, leads),
            orchestration=self._orchestration(agents),
            reporting=self._reporting_snapshot(businesses, campaigns, pages, leads, seo),
        )

    def _ai_search_visibility(
        self,
        businesses: list[BusinessProfile],
        pages: list[LandingPage],
        settings: Settings,
    ) -> GrowthAgentCard:
        brand_names = [business.name for business in businesses[:6]] or ["Agentic Growth Labs"]
        prompt = (
            "Assess how visible these brands would be in ChatGPT/OpenAI answer surfaces and "
            "return JSON with score, mentions, gaps, and actions. Brands: "
            + ", ".join(brand_names)
        )
        fallback = {
            "score": 72,
            "mentions": len(brand_names),
            "gaps": ["Need stronger comparison pages", "Need more authority citations"],
            "actions": [
                "Create explainers answering category-level buyer questions.",
                "Add structured proof points to high-intent landing pages.",
                "Publish comparison and alternative pages for competitors.",
            ],
        }
        result = self.llm.json_completion(
            system="You are an AI search visibility analyst. Reply as compact JSON only.",
            user=prompt,
            fallback=fallback,
        )
        visibility_source = "AI estimate" if settings.can_use_openai else "Demo fallback"
        return GrowthAgentCard(
            key="ai_search_visibility",
            name="AI Search Visibility Agent",
            status="active" if settings.can_use_openai else "demo_ready",
            mode="openai_live" if settings.can_use_openai else "deterministic_visibility_model",
            summary="Audits whether the brand is likely to be cited in ChatGPT-style answer journeys.",
            metrics={
                "visibility_score": int(result.get("score") or fallback["score"]),
                "tracked_brands": len(brand_names),
                "content_pages": len(pages),
                "answer_surface": "OpenAI / ChatGPT",
            },
            metric_sources={
                "visibility_score": visibility_source,
                "tracked_brands": "App DB",
                "content_pages": "App DB",
                "answer_surface": "Configuration",
            },
            recommendations=self._recommendations(result.get("actions") or fallback["actions"]),
            artifacts={"gaps": result.get("gaps") or fallback["gaps"]},
        )

    def _backlink_authority(
        self,
        business: BusinessProfile | None,
        campaigns: list[Campaign],
        dataforseo: DataForSEOClient,
    ) -> GrowthAgentCard:
        summary = dataforseo.backlink_summary(
            business.website if business else "https://agenticgrowthlabs.com",
            business.competitors if business else [],
        )
        scoped_campaigns = [campaign for campaign in campaigns if business and campaign.business_id == business.id] or campaigns
        seed_terms = [campaign.goal for campaign in scoped_campaigns[:3]]
        opportunities = dataforseo.keyword_opportunities(
            seed_terms,
            scoped_campaigns[0].target_region if scoped_campaigns else "India",
        )
        return GrowthAgentCard(
            key="backlink_authority",
            name="Backlink / Authority Agent",
            status="active" if dataforseo.is_configured else "needs_credentials",
            mode=summary.mode,
            summary="Finds authority gaps, backlink opportunities, and SEO keyword demand using DataForSEO-ready signals.",
            metrics={
                "business": business.name if business else "Default workspace",
                "domain": summary.domain,
                "backlinks": summary.backlinks,
                "referring_domains": summary.referring_domains,
                "authority_score": summary.authority_score,
            },
            metric_sources={
                "business": "App DB",
                "domain": "App DB",
                "backlinks": summary.source,
                "referring_domains": summary.source,
                "authority_score": summary.source,
            },
            recommendations=[
                {
                    "title": f"Build authority for {item['keyword']}",
                    "impact": f"{item['volume']} monthly searches, difficulty {item['difficulty']}",
                }
                for item in opportunities[:3]
            ],
            artifacts={
                "keyword_opportunities": opportunities,
                "dataforseo_error": summary.error,
                "selected_business_id": business.id if business else None,
                "selected_business_website": business.website if business else None,
                "spam_score": summary.spam_score,
            },
        )

    def _auto_refresh_approval(
        self,
        db: Session,
        campaigns: list[Campaign],
        seo,
    ) -> GrowthAgentCard:
        weak_pages = [page for page in seo.page_scores if page.overall_score < 70]
        open_recommendations = db.query(func.count(RefreshRecommendation.id)).filter(
            RefreshRecommendation.status.in_(["open", "pending_approval"])
        ).scalar() or 0
        pending_approvals = db.query(func.count(RefreshApprovalPlan.id)).filter(
            RefreshApprovalPlan.status == "pending_approval"
        ).scalar() or 0
        published_refreshes = db.query(func.count(RefreshApprovalPlan.id)).filter(
            RefreshApprovalPlan.status == "published"
        ).scalar() or 0
        return GrowthAgentCard(
            key="auto_refresh_approval",
            name="Auto Refresh + Approval Agent",
            status="active",
            mode="human_approval_guardrail",
            summary="Converts poor traffic, CTR, and conversion signals into approved refresh plans before publishing.",
            metrics={
                "pages_needing_refresh": len(weak_pages),
                "open_recommendations": open_recommendations,
                "pending_approvals": pending_approvals,
                "published_refreshes": published_refreshes,
                "campaigns_monitored": len(campaigns),
                "approval_policy": "human_review_required",
            },
            metric_sources={
                "pages_needing_refresh": self._seo_metric_source(seo),
                "open_recommendations": "App DB",
                "pending_approvals": "App DB",
                "published_refreshes": "App DB",
                "campaigns_monitored": "App DB",
                "approval_policy": "Configuration",
            },
            recommendations=[
                {"title": page.title, "impact": page.next_action}
                for page in weak_pages[:4]
            ]
            or [{"title": "No urgent refreshes", "impact": "Current published pages are above the refresh threshold."}],
            artifacts={"refresh_queue": [page.model_dump() for page in weak_pages[:8]]},
        )

    def _paid_campaigns(self, db: Session, campaigns: list[Campaign], google_ads: GoogleAdsClient) -> GrowthAgentCard:
        ads_error = None
        ads_campaigns = []
        used_google_ads = False
        if google_ads.is_configured:
            try:
                ads_campaigns = google_ads.fetch_campaigns()
                used_google_ads = bool(ads_campaigns)
            except GoogleAdsError as exc:
                ads_error = str(exc)
        if not ads_campaigns:
            ads_campaigns = [
                type(
                    "DemoCampaign",
                    (),
                    {
                        "campaign_id": campaign.id,
                        "name": campaign.name,
                        "status": "DRAFT",
                        "impressions": 0,
                        "clicks": 0,
                        "cost_micros": 0,
                        "conversions": 0.0,
                    },
                )()
                for campaign in campaigns[:3]
            ]
        impressions = sum(item.impressions for item in ads_campaigns)
        clicks = sum(item.clicks for item in ads_campaigns)
        cost = sum(item.cost_micros for item in ads_campaigns) / 1_000_000
        conversions = sum(item.conversions for item in ads_campaigns)
        draft_count = db.query(func.count(PaidAdPlan.id)).filter(PaidAdPlan.status == "draft").scalar() or 0
        pushed_count = db.query(func.count(PaidAdPlan.id)).filter(PaidAdPlan.status == "pushed_to_google").scalar() or 0
        return GrowthAgentCard(
            key="paid_campaigns",
            name="Paid Campaign Agent",
            status="active" if google_ads.is_configured and not ads_error else "pending_access",
            mode="google_ads_live" if google_ads.is_configured and not ads_error else "google_ads_review_or_credentials_pending",
            summary="Prepares Search/Performance Max campaign reporting and campaign launch readiness from Google Ads.",
            metrics={
                "campaigns": len(ads_campaigns),
                "impressions": impressions,
                "clicks": clicks,
                "cost": round(cost, 2),
                "conversions": round(conversions, 2),
                "draft_plans": draft_count,
                "pushed_plans": pushed_count,
                "error": ads_error,
            },
            metric_sources={
                "campaigns": "Live Google Ads" if used_google_ads else "App DB fallback",
                "impressions": "Live Google Ads" if used_google_ads else "Demo fallback",
                "clicks": "Live Google Ads" if used_google_ads else "Demo fallback",
                "cost": "Live Google Ads" if used_google_ads else "Demo fallback",
                "conversions": "Live Google Ads" if used_google_ads else "Demo fallback",
                "draft_plans": "App DB",
                "pushed_plans": "App DB",
                "error": "Google Ads API",
            },
            recommendations=[
                {"title": "Map top organic pages to paid ad groups", "impact": "Use SEO winners as lower-risk ad themes."},
                {"title": "Draft, validate, then approve", "impact": "Google Ads changes stay paused and owner-approved before spend."},
            ],
            artifacts={
                "campaigns": [
                    {
                        "id": item.campaign_id,
                        "name": item.name,
                        "status": item.status,
                        "impressions": item.impressions,
                        "clicks": item.clicks,
                        "cost": round(item.cost_micros / 1_000_000, 2),
                        "conversions": item.conversions,
                    }
                    for item in ads_campaigns
                ]
            },
        )

    def _client_reporting(
        self,
        businesses: list[BusinessProfile],
        campaigns: list[Campaign],
        pages: list[LandingPage],
        leads: list[Lead],
        seo,
    ) -> GrowthAgentCard:
        return GrowthAgentCard(
            key="client_reporting",
            name="Client Reporting Agent",
            status="active",
            mode="executive_report_ready",
            summary="Packages SEO, lead, campaign, and refresh outcomes into a client-ready growth report.",
            metrics={
                "clients": len(businesses),
                "campaigns": len(campaigns),
                "published_pages": len([page for page in pages if page.status == "published"]),
                "organic_clicks": seo.organic_clicks,
                "sessions": seo.sessions,
                "leads": len(leads),
            },
            metric_sources={
                "clients": "App DB",
                "campaigns": "App DB",
                "published_pages": "App DB",
                "organic_clicks": self._seo_metric_source(seo),
                "sessions": self._analytics_metric_source(seo),
                "leads": "App DB",
            },
            recommendations=[
                {"title": "Send weekly page-health report", "impact": "Shows clients exactly what changed and why."},
                {"title": "Highlight recommendations by business", "impact": "Keeps GreyRadius, Kairoz, and other clients separated."},
            ],
        )

    def _workspace_access(
        self,
        businesses: list[BusinessProfile],
        campaigns: list[Campaign],
        pages: list[LandingPage],
        leads: list[Lead],
    ) -> GrowthAgentCard:
        workspaces = self._client_workspaces(businesses, campaigns, pages, leads)
        governance_score = 100 if workspaces else 84
        return GrowthAgentCard(
            key="client_workspace_access",
            name="Client Workspace / Access Control",
            status="active",
            mode="client_partitioned_views",
            summary="Organizes every page, lead, and report by company so each client sees only their own workspace.",
            metrics={
                "workspaces": len(workspaces),
                "governance_score": governance_score,
                "roles": 3,
                "data_partitioning": "business_id",
            },
            metric_sources={
                "workspaces": "App DB",
                "governance_score": "Rule-based score",
                "roles": "Configuration",
                "data_partitioning": "Configuration",
            },
            recommendations=[
                {"title": "Use company filters for page performance", "impact": "Client demos stay clean and client-specific."},
                {"title": "Add role-based login before external rollout", "impact": "Protects multi-client data after demo phase."},
            ],
            artifacts={"workspaces": workspaces},
        )

    def _client_workspaces(
        self,
        businesses: list[BusinessProfile],
        campaigns: list[Campaign],
        pages: list[LandingPage],
        leads: list[Lead],
    ) -> list[dict[str, object]]:
        campaigns_by_business: dict[str, list[Campaign]] = {}
        pages_by_business: dict[str, list[LandingPage]] = {}
        leads_by_business: dict[str, list[Lead]] = {}
        for campaign in campaigns:
            campaigns_by_business.setdefault(campaign.business_id, []).append(campaign)
        for page in pages:
            if page.campaign:
                pages_by_business.setdefault(page.campaign.business_id, []).append(page)
        for lead in leads:
            if lead.campaign:
                leads_by_business.setdefault(lead.campaign.business_id, []).append(lead)
        return [
            {
                "business_id": business.id,
                "name": business.name,
                "industry": business.industry,
                "campaigns": len(campaigns_by_business.get(business.id, [])),
                "pages": len(pages_by_business.get(business.id, [])),
                "leads": len(leads_by_business.get(business.id, [])),
                "workspace_url": f"#growth-suite?business={business.id}",
            }
            for business in businesses
        ]

    def _reporting_snapshot(self, businesses, campaigns, pages, leads, seo) -> dict[str, object]:
        page_scores = [page.overall_score for page in seo.page_scores]
        return {
            "headline": "Client-ready SEO and growth automation report",
            "period": "last 28 days",
            "client_count": len(businesses),
            "campaign_count": len(campaigns),
            "published_pages": len([page for page in pages if page.status == "published"]),
            "lead_count": len(leads),
            "average_page_health": round(mean(page_scores), 1) if page_scores else 0,
            "next_board_action": "Review refresh queue, then approve page updates with strongest business impact.",
        }

    def _select_business(
        self,
        businesses: list[BusinessProfile],
        business_id: str | None,
    ) -> BusinessProfile | None:
        if business_id:
            explicit = next((business for business in businesses if business.id == business_id), None)
            if explicit:
                return explicit

        real_domain_business = next(
            (business for business in businesses if self._is_real_domain(business.website)),
            None,
        )
        return real_domain_business or (businesses[0] if businesses else None)

    @staticmethod
    def _selected_business_payload(business: BusinessProfile | None) -> dict[str, str | None] | None:
        if not business:
            return None
        return {
            "id": business.id,
            "name": business.name,
            "website": business.website,
            "industry": business.industry,
        }

    @staticmethod
    def _is_real_domain(website: str | None) -> bool:
        if not website:
            return False
        parsed = urlparse(website if "://" in website else f"https://{website}")
        domain = (parsed.netloc or parsed.path).removeprefix("www.").strip("/").lower()
        return bool(domain) and domain not in {"example.com", "localhost", "127.0.0.1"}

    def _orchestration(self, agents: list[GrowthAgentCard]) -> list[dict[str, object]]:
        return [
            {
                "step": index + 1,
                "agent": agent.name,
                "status": agent.status,
                "summary": agent.summary,
            }
            for index, agent in enumerate(agents)
        ]

    def _persist_execution(self, db: Session, agent: GrowthAgentCard) -> None:
        db.add(
            GrowthAgentExecution(
                agent_key=agent.key,
                status=agent.status,
                mode=agent.mode,
                summary=agent.summary,
                metrics=agent.metrics,
                recommendations=agent.recommendations,
                artifacts=agent.artifacts,
            )
        )

    def _suite_mode(self, settings: Settings, dataforseo: DataForSEOClient, google_ads: GoogleAdsClient) -> str:
        live_count = sum([settings.can_use_openai, dataforseo.is_configured, google_ads.is_configured])
        if live_count >= 3:
            return "production_integrated"
        if live_count:
            return "hybrid_live_ready"
        return "demo_ready"

    def _seo_metric_source(self, seo) -> str:
        mode = str((seo.integration_status or {}).get("mode", ""))
        if mode == "live_google_integrated":
            return "Live Google Search Console"
        if "configured" in mode:
            return "Google configured; waiting data"
        if "fallback" in mode:
            return "Demo fallback"
        return "First-party / demo"

    def _analytics_metric_source(self, seo) -> str:
        mode = str((seo.integration_status or {}).get("mode", ""))
        if mode == "live_google_integrated":
            return "Live GA4"
        if "configured" in mode:
            return "GA4 configured; waiting data"
        if "fallback" in mode:
            return "Demo fallback"
        return "First-party / demo"

    def _recommendations(self, actions: list[object]) -> list[dict[str, str]]:
        return [{"title": str(action), "impact": "Improves discoverability in AI search journeys."} for action in actions[:4]]
