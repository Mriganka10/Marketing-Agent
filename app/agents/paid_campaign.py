from __future__ import annotations

from urllib.parse import urljoin

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import Settings
from app.integrations.google_ads import GoogleAdsClient, GoogleAdsError
from app.models.entities import BusinessProfile, Campaign, LandingPage, PaidAdPlan
from app.models.schemas import PaidAdPlanDraftRequest, PaidAdPlanUpdateRequest


class PaidCampaignAgent:
    def draft_plan(self, db: Session, settings: Settings, payload: PaidAdPlanDraftRequest) -> PaidAdPlan:
        campaign = self._select_campaign(db, payload)
        business = campaign.business if campaign else self._select_business(db, payload)
        pages = self._published_pages(db, campaign, business)
        name = self._campaign_name(campaign, business)
        daily_budget_micros = int(payload.daily_budget * 1_000_000)
        plan = self._build_plan(settings, name, campaign, business, pages, daily_budget_micros, payload.currency_code)
        ad_plan = PaidAdPlan(
            business_id=business.id if business else None,
            campaign_id=campaign.id if campaign else None,
            name=name,
            objective=campaign.goal if campaign else "Generate qualified growth leads from search demand.",
            target_region=campaign.target_region if campaign else "India",
            daily_budget_micros=daily_budget_micros,
            status="draft",
            approval_status="needs_review",
            plan=plan,
        )
        db.add(ad_plan)
        db.flush()
        record_audit(
            db,
            actor="paid_campaign_agent",
            action="paid_ad_plan_drafted",
            entity_type="paid_ad_plan",
            entity_id=ad_plan.id,
            metadata={"campaign_id": ad_plan.campaign_id, "business_id": ad_plan.business_id},
        )
        db.commit()
        db.refresh(ad_plan)
        return ad_plan

    def list_plans(self, db: Session) -> list[PaidAdPlan]:
        return db.query(PaidAdPlan).order_by(PaidAdPlan.created_at.desc()).limit(50).all()

    def update_plan(self, db: Session, plan: PaidAdPlan, payload: PaidAdPlanUpdateRequest) -> PaidAdPlan:
        plan_payload = dict(plan.plan or {})
        if payload.name is not None:
            plan.name = payload.name
            plan_payload["name"] = payload.name
        if payload.objective is not None:
            plan.objective = payload.objective
            plan_payload["objective"] = payload.objective
        if payload.target_region is not None:
            plan.target_region = payload.target_region
            plan_payload["target_region"] = payload.target_region
        if payload.daily_budget is not None:
            plan.daily_budget_micros = int(payload.daily_budget * 1_000_000)
            plan_payload["daily_budget_micros"] = plan.daily_budget_micros
        if payload.plan is not None:
            plan_payload = {**plan_payload, **payload.plan}
        plan.plan = plan_payload
        plan.status = "draft"
        plan.approval_status = "needs_review"
        record_audit(
            db,
            actor="paid_campaign_agent",
            action="paid_ad_plan_updated",
            entity_type="paid_ad_plan",
            entity_id=plan.id,
        )
        db.commit()
        db.refresh(plan)
        return plan

    def validate_with_google(self, db: Session, settings: Settings, plan: PaidAdPlan) -> PaidAdPlan:
        client = GoogleAdsClient(settings)
        try:
            response = (
                client.update_campaign_controls(
                    campaign_resource_name=plan.google_campaign_resource_name or "",
                    budget_resource_name=plan.google_budget_resource_name,
                    name=plan.name,
                    status="PAUSED",
                    daily_budget_micros=plan.daily_budget_micros,
                    validate_only=True,
                )
                if plan.google_campaign_resource_name
                else client.validate_campaign_plan(plan.plan)
            )
            plan.validation_response = response
            plan.status = "validated"
            plan.approval_status = "ready_for_owner_approval"
        except GoogleAdsError as exc:
            plan.validation_response = {"error": str(exc)}
            plan.status = "validation_failed"
            plan.approval_status = "needs_review"
        record_audit(
            db,
            actor="paid_campaign_agent",
            action="paid_ad_plan_validated",
            entity_type="paid_ad_plan",
            entity_id=plan.id,
            metadata={"status": plan.status},
        )
        db.commit()
        db.refresh(plan)
        return plan

    def push_to_google(self, db: Session, settings: Settings, plan: PaidAdPlan) -> PaidAdPlan:
        client = GoogleAdsClient(settings)
        try:
            response = (
                client.update_campaign_controls(
                    campaign_resource_name=plan.google_campaign_resource_name or "",
                    budget_resource_name=plan.google_budget_resource_name,
                    name=plan.name,
                    status=plan.plan.get("campaign_status") or "PAUSED",
                    daily_budget_micros=plan.daily_budget_micros,
                    validate_only=False,
                )
                if plan.google_campaign_resource_name
                else client.create_campaign_from_plan(plan.plan)
            )
            plan.push_response = response
            plan.status = "pushed_to_google"
            plan.approval_status = "approved"
            self._capture_resource_names(plan, response)
        except GoogleAdsError as exc:
            plan.push_response = {"error": str(exc)}
            plan.status = "push_failed"
            plan.approval_status = "needs_review"
        record_audit(
            db,
            actor="paid_campaign_agent",
            action="paid_ad_plan_pushed",
            entity_type="paid_ad_plan",
            entity_id=plan.id,
            metadata={"status": plan.status},
        )
        db.commit()
        db.refresh(plan)
        return plan

    def _select_campaign(self, db: Session, payload: PaidAdPlanDraftRequest) -> Campaign | None:
        if payload.campaign_id:
            return db.get(Campaign, payload.campaign_id)
        query = db.query(Campaign).order_by(Campaign.created_at.desc())
        if payload.business_id:
            query = query.filter(Campaign.business_id == payload.business_id)
        return query.first()

    def _select_business(self, db: Session, payload: PaidAdPlanDraftRequest) -> BusinessProfile | None:
        if payload.business_id:
            return db.get(BusinessProfile, payload.business_id)
        return db.query(BusinessProfile).order_by(BusinessProfile.created_at.desc()).first()

    def _published_pages(
        self,
        db: Session,
        campaign: Campaign | None,
        business: BusinessProfile | None,
    ) -> list[LandingPage]:
        query = db.query(LandingPage).filter(LandingPage.status == "published").order_by(LandingPage.created_at.desc())
        if campaign:
            query = query.filter(LandingPage.campaign_id == campaign.id)
        elif business:
            query = query.join(Campaign).filter(Campaign.business_id == business.id)
        return query.limit(6).all()

    def _campaign_name(self, campaign: Campaign | None, business: BusinessProfile | None) -> str:
        prefix = business.name if business else "Agentic Growth Labs"
        suffix = campaign.name if campaign else "Search Growth"
        return f"{prefix} - {suffix} - Search"

    def _build_plan(
        self,
        settings: Settings,
        name: str,
        campaign: Campaign | None,
        business: BusinessProfile | None,
        pages: list[LandingPage],
        daily_budget_micros: int,
        currency_code: str,
    ) -> dict[str, object]:
        page = pages[0] if pages else None
        keywords = self._keywords(campaign, business, pages)
        final_url = (
            urljoin(settings.public_base_url.rstrip("/") + "/", f"p/{page.slug}")
            if page
            else settings.public_base_url
        )
        brand = business.name if business else "Agentic Growth Labs"
        offer = business.offers[0] if business and business.offers else "AI marketing automation"
        return {
            "name": name[:180],
            "objective": campaign.goal if campaign else "Generate qualified growth leads from search demand.",
            "target_region": campaign.target_region if campaign else "India",
            "currency_code": currency_code,
            "daily_budget_micros": daily_budget_micros,
            "campaign_status": "PAUSED",
            "ad_group_status": "PAUSED",
            "ad_group_name": f"{brand[:80]} high-intent search",
            "cpc_bid_micros": 1_000_000,
            "final_urls": [final_url],
            "keywords": [{"text": keyword[:80], "match_type": "PHRASE"} for keyword in keywords],
            "headlines": self._headlines(brand, offer),
            "descriptions": self._descriptions(brand, campaign, business),
            "safety": {
                "default_google_status": "PAUSED",
                "requires_owner_approval": True,
                "spend_guardrail": "No campaign is pushed unless approve_google_push=true and mode=publish.",
            },
        }

    def _keywords(
        self,
        campaign: Campaign | None,
        business: BusinessProfile | None,
        pages: list[LandingPage],
    ) -> list[str]:
        values: list[str] = []
        if campaign:
            values.extend([campaign.goal, campaign.name])
        if business:
            values.extend(business.offers)
            values.extend([business.industry, f"{business.industry} automation", f"{business.name} alternative"])
        for page in pages:
            seo_keywords = page.seo.get("keywords") if isinstance(page.seo, dict) else None
            if isinstance(seo_keywords, str):
                values.extend([item.strip() for item in seo_keywords.split(",")])
            values.append(page.title)
        cleaned = []
        for value in values:
            item = " ".join(str(value).split()).lower()
            if len(item) >= 3 and item not in cleaned:
                cleaned.append(item)
        return cleaned[:12] or ["ai marketing automation", "seo landing page automation", "lead capture automation"]

    def _headlines(self, brand: str, offer: str) -> list[str]:
        return [
            f"{brand[:18]} Growth",
            "AI Marketing Agents",
            "Automate SEO Pages",
            "Capture Qualified Leads",
            "Scale Demand Generation",
            f"{offer[:28]}",
            "Book A Growth Demo",
        ]

    def _descriptions(
        self,
        brand: str,
        campaign: Campaign | None,
        business: BusinessProfile | None,
    ) -> list[str]:
        proposition = business.value_proposition if business else "Launch pages, capture leads, and improve growth campaigns."
        goal = campaign.goal if campaign else "Generate qualified marketing leads."
        return [
            proposition[:90],
            goal[:90],
            f"{brand} helps teams turn search demand into measurable pipeline."[:90],
            "Start with approval-safe AI campaigns and page-level analytics."[:90],
        ]

    def _capture_resource_names(self, plan: PaidAdPlan, response: dict[str, object]) -> None:
        payload = response.get("response") if isinstance(response, dict) else None
        results = payload.get("mutateOperationResponses", []) if isinstance(payload, dict) else []
        for item in results:
            if "campaignBudgetResult" in item:
                plan.google_budget_resource_name = item["campaignBudgetResult"].get("resourceName")
            if "campaignResult" in item:
                plan.google_campaign_resource_name = item["campaignResult"].get("resourceName")
            if "adGroupResult" in item:
                plan.google_ad_group_resource_name = item["adGroupResult"].get("resourceName")
