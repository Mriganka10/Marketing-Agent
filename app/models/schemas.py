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
