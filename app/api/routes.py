from __future__ import annotations

import json
from html import escape
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.analytics_refresh import AnalyticsRefreshAgent
from app.agents.auto_refresh_approval import AutoRefreshApprovalAgent
from app.agents.business_memory import BusinessMemoryAgent
from app.agents.content import ContentPageCreationAgent
from app.agents.lead_capture import LeadCaptureAgent
from app.agents.llm import LLMService
from app.agents.growth_suite import GrowthSuiteAgent
from app.agents.orchestrator import MarketingOrchestrator
from app.agents.paid_campaign import PaidCampaignAgent
from app.agents.research import ResearchAgent
from app.agents.seo_analytics import SeoAnalyticsAgent
from app.core.config import Settings, get_settings
from app.core.brand_theme import public_theme_style, theme_for_business, theme_from_dict
from app.core.content_formatting import coerce_text, normalize_sections
from app.core.database import get_db
from app.core.security import require_api_key
from app.models.entities import (
    AuditEvent,
    BusinessProfile,
    Campaign,
    LandingPage,
    Lead,
    PaidAdPlan,
    RefreshRecommendation,
)
from app.models.schemas import (
    BusinessProfileCreate,
    BusinessProfileRead,
    CampaignCreate,
    CampaignRead,
    DashboardSummary,
    LandingPageRead,
    LeadCreate,
    LeadRead,
    PageEventCreate,
    PaidAdPlanDraftRequest,
    PaidAdPlanPushRequest,
    PaidAdPlanRead,
    PaidAdPlanUpdateRequest,
    RecommendationRead,
    RefreshApprovalRequest,
    RefreshPublishRequest,
    RefreshRejectionRequest,
    RunRequest,
    RunSummary,
    GrowthSuiteOverview,
    SeoOverview,
)

router = APIRouter()


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(
        "app/static/index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


def get_llm(settings: Settings = Depends(get_settings)) -> LLMService:
    return LLMService(settings)


def get_orchestrator(llm: LLMService = Depends(get_llm)) -> MarketingOrchestrator:
    return MarketingOrchestrator(
        research_agent=ResearchAgent(llm),
        content_agent=ContentPageCreationAgent(llm),
        analytics_agent=AnalyticsRefreshAgent(),
    )


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str | bool | int]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "openai_configured": settings.can_use_openai,
        "dataforseo_configured": settings.can_use_dataforseo,
        "google_ads_configured": settings.can_use_google_ads,
        "ssm_runtime_loading": settings.ssm_enabled,
        "ssm_parameters_loaded": settings.ssm_loaded_parameters,
    }


@router.get("/robots.txt", include_in_schema=False)
def robots(settings: Settings = Depends(get_settings)) -> Response:
    base = settings.public_base_url.rstrip("/")
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            f"Sitemap: {base}/sitemap.xml",
            "",
        ]
    )
    return Response(content=body, media_type="text/plain")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> Response:
    base = settings.public_base_url.rstrip() + "/"
    pages = db.query(LandingPage).filter(LandingPage.status == "published").all()
    urls = [
        (
            settings.public_base_url.rstrip("/"),
            "daily",
            "0.9",
        )
    ] + [
        (
            urljoin(base, f"p/{page.slug}"),
            "weekly",
            "0.8",
        )
        for page in pages
    ]
    entries = "\n".join(
        f"<url><loc>{escape(loc)}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>"
        for loc, freq, priority in urls
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )
    return Response(content=body, media_type="application/xml")


@router.post(
    "/api/businesses",
    response_model=BusinessProfileRead,
    dependencies=[Depends(require_api_key)],
)
def create_business(payload: BusinessProfileCreate, db: Session = Depends(get_db)) -> BusinessProfile:
    return BusinessMemoryAgent().upsert_business(db, payload)


@router.get("/api/businesses", response_model=list[BusinessProfileRead])
def list_businesses(db: Session = Depends(get_db)) -> list[BusinessProfile]:
    return db.query(BusinessProfile).order_by(BusinessProfile.created_at.desc()).all()


@router.post(
    "/api/campaigns",
    response_model=CampaignRead,
    dependencies=[Depends(require_api_key)],
)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)) -> Campaign:
    if not db.get(BusinessProfile, payload.business_id):
        raise HTTPException(status_code=404, detail="Business profile not found.")
    return BusinessMemoryAgent().create_campaign(db, payload)


@router.get("/api/campaigns", response_model=list[CampaignRead])
def list_campaigns(db: Session = Depends(get_db)) -> list[Campaign]:
    return db.query(Campaign).order_by(Campaign.created_at.desc()).all()


@router.post(
    "/api/runs",
    response_model=RunSummary,
    dependencies=[Depends(require_api_key)],
)
def run_campaign(
    payload: RunRequest,
    db: Session = Depends(get_db),
    orchestrator: MarketingOrchestrator = Depends(get_orchestrator),
) -> dict[str, object]:
    campaign = db.get(Campaign, payload.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return orchestrator.run(db, campaign, publish_pages=payload.publish_pages)


@router.get("/api/pages", response_model=list[LandingPageRead])
def list_pages(db: Session = Depends(get_db)) -> list[LandingPage]:
    pages = db.query(LandingPage).order_by(LandingPage.created_at.desc()).all()
    _repair_page_content(db, pages)
    return pages


@router.get("/api/pages/{page_id}", response_model=LandingPageRead)
def get_page(page_id: str, db: Session = Depends(get_db)) -> LandingPage:
    page = db.get(LandingPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found.")
    _repair_page_content(db, [page])
    return page


@router.post("/api/leads", response_model=LeadRead)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)) -> Lead:
    if not db.get(Campaign, payload.campaign_id):
        raise HTTPException(status_code=404, detail="Campaign not found.")
    if payload.page_id and not db.get(LandingPage, payload.page_id):
        raise HTTPException(status_code=404, detail="Landing page not found.")
    return LeadCaptureAgent().capture(db, payload)


@router.get("/api/leads", response_model=list[LeadRead])
def list_leads(db: Session = Depends(get_db)) -> list[Lead]:
    return db.query(Lead).order_by(Lead.created_at.desc()).limit(100).all()


@router.post(
    "/api/campaigns/{campaign_id}/refresh",
    response_model=list[RecommendationRead],
    dependencies=[Depends(require_api_key)],
)
def refresh_campaign(campaign_id: str, db: Session = Depends(get_db)) -> list[RefreshRecommendation]:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return AnalyticsRefreshAgent().recommend(db, campaign)


@router.get("/api/recommendations", response_model=list[RecommendationRead])
def list_recommendations(db: Session = Depends(get_db)) -> list[RefreshRecommendation]:
    return db.query(RefreshRecommendation).order_by(RefreshRecommendation.created_at.desc()).limit(50).all()


def _refresh_recommendation(db: Session, recommendation_id: str) -> RefreshRecommendation:
    recommendation = db.get(RefreshRecommendation, recommendation_id)
    if not recommendation:
        raise HTTPException(status_code=404, detail="Refresh recommendation not found.")
    return recommendation


def _run_refresh_action(action):
    try:
        return action()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/api/recommendations/{recommendation_id}/rewrite",
    response_model=RecommendationRead,
    dependencies=[Depends(require_api_key)],
)
def draft_recommendation_rewrite(
    recommendation_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RefreshRecommendation:
    recommendation = _refresh_recommendation(db, recommendation_id)
    agent = AutoRefreshApprovalAgent(LLMService(settings))
    _run_refresh_action(lambda: agent.draft_rewrite(db, recommendation))
    db.refresh(recommendation)
    return recommendation


@router.post(
    "/api/recommendations/{recommendation_id}/approve",
    response_model=RecommendationRead,
    dependencies=[Depends(require_api_key)],
)
def approve_recommendation_rewrite(
    recommendation_id: str,
    payload: RefreshApprovalRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RefreshRecommendation:
    recommendation = _refresh_recommendation(db, recommendation_id)
    if not recommendation.refresh_plan:
        raise HTTPException(status_code=409, detail="Generate a rewrite draft before approving it.")
    agent = AutoRefreshApprovalAgent(LLMService(settings))
    _run_refresh_action(
        lambda: agent.approve(db, recommendation.refresh_plan, approved_by=payload.approved_by)
    )
    db.refresh(recommendation)
    return recommendation


@router.post(
    "/api/recommendations/{recommendation_id}/reject",
    response_model=RecommendationRead,
    dependencies=[Depends(require_api_key)],
)
def reject_recommendation_rewrite(
    recommendation_id: str,
    payload: RefreshRejectionRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RefreshRecommendation:
    recommendation = _refresh_recommendation(db, recommendation_id)
    if not recommendation.refresh_plan:
        raise HTTPException(status_code=409, detail="There is no rewrite draft to reject.")
    agent = AutoRefreshApprovalAgent(LLMService(settings))
    _run_refresh_action(
        lambda: agent.reject(db, recommendation.refresh_plan, reason=payload.reason)
    )
    db.refresh(recommendation)
    return recommendation


@router.post(
    "/api/recommendations/{recommendation_id}/publish",
    response_model=RecommendationRead,
    dependencies=[Depends(require_api_key)],
)
def publish_recommendation_rewrite(
    recommendation_id: str,
    payload: RefreshPublishRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RefreshRecommendation:
    recommendation = _refresh_recommendation(db, recommendation_id)
    if not payload.confirm_publish:
        raise HTTPException(
            status_code=400,
            detail="Publishing requires confirm_publish=true after explicit rewrite approval.",
        )
    if not recommendation.refresh_plan:
        raise HTTPException(status_code=409, detail="There is no rewrite draft to publish.")
    agent = AutoRefreshApprovalAgent(LLMService(settings))
    _run_refresh_action(lambda: agent.publish(db, recommendation.refresh_plan))
    db.refresh(recommendation)
    return recommendation


@router.post("/api/events")
def create_page_event(
    payload: PageEventCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if payload.page_id and not db.get(LandingPage, payload.page_id):
        raise HTTPException(status_code=404, detail="Landing page not found.")
    event = SeoAnalyticsAgent().record_event(
        db,
        payload,
        user_agent=request.headers.get("user-agent"),
    )
    return {"id": event.id, "status": "recorded"}


@router.get("/api/seo/overview", response_model=SeoOverview)
def seo_overview(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SeoOverview:
    return SeoAnalyticsAgent().overview(db, settings)


@router.get("/api/seo/integrations")
def seo_integrations(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return SeoAnalyticsAgent().integration_status(db, settings)


@router.get("/api/google-reports")
def google_reports(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return SeoAnalyticsAgent().google_reports(db, settings)


@router.post(
    "/api/seo/sync",
    dependencies=[Depends(require_api_key)],
)
def sync_seo_metrics(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    return SeoAnalyticsAgent().sync_metrics(db, settings)


@router.get("/api/growth/overview", response_model=GrowthSuiteOverview)
def growth_overview(
    business_id: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    llm: LLMService = Depends(get_llm),
) -> GrowthSuiteOverview:
    return GrowthSuiteAgent(llm).overview(db, settings, business_id=business_id)


@router.post(
    "/api/growth/sync",
    response_model=GrowthSuiteOverview,
    dependencies=[Depends(require_api_key)],
)
def sync_growth_agents(
    business_id: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    llm: LLMService = Depends(get_llm),
) -> GrowthSuiteOverview:
    return GrowthSuiteAgent(llm).overview(db, settings, persist=True, business_id=business_id)


@router.get("/api/ads/plans", response_model=list[PaidAdPlanRead])
def list_paid_ad_plans(db: Session = Depends(get_db)) -> list[PaidAdPlan]:
    return PaidCampaignAgent().list_plans(db)


@router.post(
    "/api/ads/plans/draft",
    response_model=PaidAdPlanRead,
    dependencies=[Depends(require_api_key)],
)
def draft_paid_ad_plan(
    payload: PaidAdPlanDraftRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PaidAdPlan:
    if payload.campaign_id and not db.get(Campaign, payload.campaign_id):
        raise HTTPException(status_code=404, detail="Campaign not found.")
    if payload.business_id and not db.get(BusinessProfile, payload.business_id):
        raise HTTPException(status_code=404, detail="Business profile not found.")
    return PaidCampaignAgent().draft_plan(db, settings, payload)


@router.patch(
    "/api/ads/plans/{plan_id}",
    response_model=PaidAdPlanRead,
    dependencies=[Depends(require_api_key)],
)
def update_paid_ad_plan(
    plan_id: str,
    payload: PaidAdPlanUpdateRequest,
    db: Session = Depends(get_db),
) -> PaidAdPlan:
    plan = db.get(PaidAdPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Paid ad plan not found.")
    return PaidCampaignAgent().update_plan(db, plan, payload)


@router.post(
    "/api/ads/plans/{plan_id}/validate",
    response_model=PaidAdPlanRead,
    dependencies=[Depends(require_api_key)],
)
def validate_paid_ad_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PaidAdPlan:
    plan = db.get(PaidAdPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Paid ad plan not found.")
    return PaidCampaignAgent().validate_with_google(db, settings, plan)


@router.post(
    "/api/ads/plans/{plan_id}/push",
    response_model=PaidAdPlanRead,
    dependencies=[Depends(require_api_key)],
)
def push_paid_ad_plan(
    plan_id: str,
    payload: PaidAdPlanPushRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> PaidAdPlan:
    plan = db.get(PaidAdPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Paid ad plan not found.")
    if payload.mode == "validate_only":
        return PaidCampaignAgent().validate_with_google(db, settings, plan)
    if not payload.approve_google_push:
        raise HTTPException(
            status_code=400,
            detail="Live Google Ads push requires approve_google_push=true and mode=publish.",
        )
    return PaidCampaignAgent().push_to_google(db, settings, plan)


@router.get("/api/audit")
def list_audit(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100).all()
    return [
        {
            "id": event.id,
            "actor": event.actor,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "metadata": event.event_metadata,
            "created_at": event.created_at,
        }
        for event in events
    ]


@router.get("/api/dashboard", response_model=DashboardSummary)
def dashboard(db: Session = Depends(get_db)) -> DashboardSummary:
    pages = db.query(LandingPage).all()
    visits = sum(page.visits for page in pages)
    leads = db.query(func.count(Lead.id)).scalar() or 0
    # Leads are the authoritative App DB conversion record. LandingPage.conversions is
    # retained as a historical per-page counter, but can drift when lead records are
    # deleted or repaired and must not drive the workspace-wide conversion rate.
    conversions = leads
    recent_leads = db.query(Lead).order_by(Lead.created_at.desc()).limit(5).all()
    recommendations = (
        db.query(RefreshRecommendation).order_by(RefreshRecommendation.created_at.desc()).limit(5).all()
    )
    return DashboardSummary(
        businesses=db.query(func.count(BusinessProfile.id)).scalar() or 0,
        campaigns=db.query(func.count(Campaign.id)).scalar() or 0,
        pages=len(pages),
        leads=leads,
        visits=visits,
        conversions=conversions,
        conversion_rate=round((conversions / visits) * 100, 2) if visits else 0,
        recent_leads=recent_leads,
        recommendations=recommendations,
    )


@router.get("/p/{slug}", response_class=HTMLResponse)
def public_landing_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> str:
    page = db.query(LandingPage).filter(LandingPage.slug == slug, LandingPage.status == "published").first()
    if not page:
        raise HTTPException(status_code=404, detail="Landing page not found.")
    _repair_page_content(db, [page])
    business = page.campaign.business if page.campaign else None
    brand_name = escape(business.name if business else "Marketing Agent")
    theme = theme_from_dict(page.seo.get("brand_theme")) or theme_for_business(
        business.name if business else None,
        business.website if business else None,
    )
    theme_style = public_theme_style(theme)
    logo_markup = (
        f'<img class="brand-logo" src="{escape(theme.logo_url, quote=True)}" alt="{brand_name} logo" />'
        if theme.logo_url
        else f'<span class="brand-name">{brand_name}</span>'
    )
    page.visits += 1
    db.commit()
    SeoAnalyticsAgent().record_event(
        db,
        PageEventCreate(
            page_id=page.id,
            campaign_id=page.campaign_id,
            event_type="page_view",
            path=str(request.url.path),
            referrer=request.headers.get("referer"),
            event_metadata={"source": "server_render"},
        ),
        user_agent=request.headers.get("user-agent"),
    )
    sections = "".join(
        f"<section><h2>{escape(str(section.get('heading', '')))}</h2>"
        f"<p>{escape(str(section.get('body', '')))}</p></section>"
        for section in page.sections
    )
    title = escape(page.title)
    hero = escape(page.hero)
    cta = escape(page.cta)
    description = escape(str(page.seo.get("description", page.hero)))
    canonical = escape(urljoin(settings.public_base_url.rstrip("/") + "/", f"p/{page.slug}"), quote=True)
    keywords = ", ".join(str(item) for item in page.seo.get("keywords", []))
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "name": brand_name,
                "url": settings.public_base_url,
            },
            {
                "@type": "Service",
                "name": page.title,
                "description": str(page.seo.get("description", page.hero)),
                "provider": {"@type": "Organization", "name": brand_name},
                "url": canonical,
                "areaServed": page.campaign.target_region if page.campaign else "Global",
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Home",
                        "item": settings.public_base_url,
                    },
                    {"@type": "ListItem", "position": 2, "name": page.title, "item": canonical},
                ],
            },
        ],
    }
    ga4_script = (
        f"""
  <script async src="https://www.googletagmanager.com/gtag/js?id={escape(settings.ga4_measurement_id, quote=True)}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{escape(settings.ga4_measurement_id, quote=True)}', {{
      page_path: '/p/{escape(page.slug, quote=True)}',
      page_title: '{title}'
    }});
  </script>"""
        if settings.ga4_measurement_id
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <meta name="keywords" content="{escape(keywords, quote=True)}" />
  <link rel="canonical" href="{canonical}" />
  <meta property="og:title" content="{title}" />
  <meta property="og:description" content="{description}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:type" content="website" />
  <link rel="stylesheet" href="/static/styles.css?v=growth-suite-20260707-1" />
  <style>{theme_style}</style>
  <script type="application/ld+json">{json.dumps(schema)}</script>
  {ga4_script}
</head>
<body class="public-page">
  <main class="public-shell">
    <header class="public-brand-header">
      <a class="brand-home" href="/">{logo_markup}</a>
    </header>
    <section class="public-hero">
      <div>
        <p class="eyebrow">Generated demand page</p>
        <h1>{title}</h1>
        <p>{hero}</p>
      </div>
      <form class="lead-form" data-campaign="{page.campaign_id}" data-page="{page.id}">
        <h2>{cta}</h2>
        <input name="name" required placeholder="Name" />
        <input name="email" required type="email" placeholder="Work email" />
        <input name="company" placeholder="Company" />
        <textarea name="message" placeholder="What are you trying to grow?"></textarea>
        <button type="submit">Send request</button>
        <p class="form-status"></p>
      </form>
    </section>
    <div class="public-sections">{sections}</div>
  </main>
  <script src="/static/public.js?v=growth-suite-20260707-1"></script>
</body>
</html>"""


def _repair_page_content(db: Session, pages: list[LandingPage]) -> None:
    changed = False
    fallback_sections = [
        {
            "heading": "Why it matters",
            "body": "This page is designed to turn buyer intent into a clear next step.",
        }
    ]
    for page in pages:
        hero = coerce_text(page.hero, "")
        cta = coerce_text(page.cta, "Request a consultation")[:160]
        sections = normalize_sections(page.sections, fallback_sections)
        if hero != page.hero:
            page.hero = hero
            changed = True
        if cta != page.cta:
            page.cta = cta
            changed = True
        if sections != page.sections:
            page.sections = sections
            changed = True
    if changed:
        db.commit()
