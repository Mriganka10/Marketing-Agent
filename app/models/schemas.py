from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class BusinessProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    website: HttpUrl | None = None
    industry: str = Field(min_length=2, max_length=120)
    audience: str = Field(min_length=8)
    value_proposition: str = Field(min_length=8)
    offers: list[str] = []
    competitors: list[str] = []
    tone: str = "professional"


class BusinessProfileRead(BusinessProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class CampaignCreate(BaseModel):
    business_id: str
    name: str = Field(min_length=2, max_length=160)
    goal: str = Field(min_length=8)
    target_region: str = "United States"


class CampaignRead(CampaignCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    created_at: datetime
    updated_at: datetime


class DemandSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    keyword: str
    intent: str
    region: str
    priority_score: float
    rationale: str
    created_at: datetime

class LandingPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    slug: str
    title: str
    hero: str
    sections: list[dict[str, Any]]
    cta: str
    seo: dict[str, Any]
    status: str
    visits: int
    conversions: int
    created_at: datetime
    updated_at: datetime

class LeadCreate(BaseModel):
    campaign_id: str
    page_id: str | None = None
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    company: str | None = None
    message: str | None = None
    source: str = "landing_page"


class LeadRead(LeadCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    score: float
    status: str
    created_at: datetime

class RecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    page_id: str | None
    severity: str
    recommendation: str
    expected_impact: str
    status: str
    created_at: datetime


class SeoSearchMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    page_id: str
    date: datetime
    query: str
    country: str
    device: str
    impressions: int
    clicks: int
    ctr: float
    average_position: float
    source: str


class AnalyticsPageMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    page_id: str
    date: datetime
    sessions: int
    engaged_sessions: int
    cta_clicks: int
    form_starts: int
    form_submits: int
    scroll_75: int
    traffic_source: str
    device: str
    country: str
    source: str


class PageEventCreate(BaseModel):
    page_id: str | None = None
    campaign_id: str | None = None
    event_type: str = Field(min_length=2, max_length=80)
    session_id: str | None = None
    path: str | None = None
    referrer: str | None = None
    event_metadata: dict[str, Any] = {}


class PageRefreshVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    page_id: str
    version_number: int
    change_summary: str
    old_title: str | None
    new_title: str | None
    old_hero: str | None
    new_hero: str | None
    old_cta: str | None
    new_cta: str | None
    created_by: str
    created_at: datetime


class SeoPageScore(BaseModel):
    page_id: str
    business_id: str | None = None
    business_name: str | None = None
    slug: str
    title: str
    url: str
    technical_score: float
    content_score: float
    search_score: float
    conversion_score: float
    overall_score: float
    impressions: int
    clicks: int
    ctr: float
    average_position: float
    sessions: int
    engaged_sessions: int
    leads: int
    conversion_rate: float
    diagnosis: str
    next_action: str


class SeoOverview(BaseModel):
    pages_published: int
    indexed_pages: int
    organic_impressions: int
    organic_clicks: int
    ctr: float
    average_position: float
    sessions: int
    engaged_sessions: int
    leads: int
    conversion_rate: float
    pages_needing_refresh: int
    top_queries: list[dict[str, Any]]
    integration_status: dict[str, Any]
    page_scores: list[SeoPageScore]

class RunRequest(BaseModel):
    campaign_id: str
    publish_pages: bool = True


class RunSummary(BaseModel):
    campaign: CampaignRead
    demand_signals: list[DemandSignalRead]
    pages: list[LandingPageRead]
    recommendations: list[RecommendationRead]


class DashboardSummary(BaseModel):
    businesses: int
    campaigns: int
    pages: int
    leads: int
    visits: int
    conversions: int
    conversion_rate: float
    recent_leads: list[LeadRead]
    recommendations: list[RecommendationRead]


class GrowthAgentCard(BaseModel):
    key: str
    name: str
    status: str
    mode: str
    summary: str
    metrics: dict[str, Any]
    recommendations: list[dict[str, Any]]
    artifacts: dict[str, Any] = {}
    updated_at: datetime | None = None


class GrowthSuiteOverview(BaseModel):
    mode: str
    readiness: dict[str, Any]
    agents: list[GrowthAgentCard]
    client_workspaces: list[dict[str, Any]]
    orchestration: list[dict[str, Any]]
    reporting: dict[str, Any]
