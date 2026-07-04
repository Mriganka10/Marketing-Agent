from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.analytics_refresh import AnalyticsRefreshAgent
from app.agents.business_memory import BusinessMemoryAgent
from app.agents.content import ContentPageCreationAgent
from app.agents.lead_capture import LeadCaptureAgent
from app.agents.llm import LLMService
from app.agents.orchestrator import MarketingOrchestrator
from app.agents.research import ResearchAgent
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
    RecommendationRead,
    RunRequest,
    RunSummary,
)

router = APIRouter()


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse("app/static/index.html")


def get_llm(settings: Settings = Depends(get_settings)) -> LLMService:
    return LLMService(settings)


def get_orchestrator(llm: LLMService = Depends(get_llm)) -> MarketingOrchestrator:
    return MarketingOrchestrator(
        research_agent=ResearchAgent(llm),
        content_agent=ContentPageCreationAgent(llm),
        analytics_agent=AnalyticsRefreshAgent(),
    )


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "openai_configured": settings.can_use_openai,
    }


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
    conversions = sum(page.conversions for page in pages)
    recent_leads = db.query(Lead).order_by(Lead.created_at.desc()).limit(5).all()
    recommendations = (
        db.query(RefreshRecommendation).order_by(RefreshRecommendation.created_at.desc()).limit(5).all()
    )
    return DashboardSummary(
        businesses=db.query(func.count(BusinessProfile.id)).scalar() or 0,
        campaigns=db.query(func.count(Campaign.id)).scalar() or 0,
        pages=len(pages),
        leads=db.query(func.count(Lead.id)).scalar() or 0,
        visits=visits,
        conversions=conversions,
        conversion_rate=round((conversions / visits) * 100, 2) if visits else 0,
        recent_leads=recent_leads,
        recommendations=recommendations,
    )


@router.get("/p/{slug}", response_class=HTMLResponse)
def public_landing_page(slug: str, request: Request, db: Session = Depends(get_db)) -> str:
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
    sections = "".join(
        f"<section><h2>{escape(str(section.get('heading', '')))}</h2>"
        f"<p>{escape(str(section.get('body', '')))}</p></section>"
        for section in page.sections
    )
    title = escape(page.title)
    hero = escape(page.hero)
    cta = escape(page.cta)
    description = escape(str(page.seo.get("description", page.hero)))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content="{description}" />
  <link rel="stylesheet" href="/static/styles.css?v=brand-theme-20260705" />
  <style>{theme_style}</style>
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
  <script src="/static/public.js"></script>
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
