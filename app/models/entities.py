from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def new_id() -> str:
    return str(uuid4())


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    website: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str] = mapped_column(String(120), nullable=False)
    audience: Mapped[str] = mapped_column(Text, nullable=False)
    value_proposition: Mapped[str] = mapped_column(Text, nullable=False)
    offers: Mapped[list[str]] = mapped_column(JSON, default=list)
    competitors: Mapped[list[str]] = mapped_column(JSON, default=list)
    tone: Mapped[str] = mapped_column(String(80), default="professional")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="business")
    seo_connections: Mapped[list["SeoIntegrationConnection"]] = relationship(back_populates="business")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("business_profiles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    target_region: Mapped[str] = mapped_column(String(120), default="United States")
    status: Mapped[str] = mapped_column(String(40), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    business: Mapped[BusinessProfile] = relationship(back_populates="campaigns")
    demand_signals: Mapped[list["DemandSignal"]] = relationship(back_populates="campaign")
    pages: Mapped[list["LandingPage"]] = relationship(back_populates="campaign")
    leads: Mapped[list["Lead"]] = relationship(back_populates="campaign")
    seo_runs: Mapped[list["SeoRecommendationRun"]] = relationship(back_populates="campaign")


class DemandSignal(Base):
    __tablename__ = "demand_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(String(180), nullable=False)
    intent: Mapped[str] = mapped_column(String(80), nullable=False)
    region: Mapped[str] = mapped_column(String(120), nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    campaign: Mapped[Campaign] = relationship(back_populates="demand_signals")


class LandingPage(Base):
    __tablename__ = "landing_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    hero: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    cta: Mapped[str] = mapped_column(String(160), nullable=False)
    seo: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    visits: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    campaign: Mapped[Campaign] = relationship(back_populates="pages")
    leads: Mapped[list["Lead"]] = relationship(back_populates="page")
    search_metrics: Mapped[list["SeoSearchMetric"]] = relationship(back_populates="page")
    analytics_metrics: Mapped[list["AnalyticsPageMetric"]] = relationship(back_populates="page")
    events: Mapped[list["PageEvent"]] = relationship(back_populates="page")
    refresh_versions: Mapped[list["PageRefreshVersion"]] = relationship(back_populates="page")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    page_id: Mapped[str | None] = mapped_column(ForeignKey("landing_pages.id"))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(180))
    message: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), default="new")
    source: Mapped[str] = mapped_column(String(120), default="landing_page")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    campaign: Mapped[Campaign] = relationship(back_populates="leads")
    page: Mapped[LandingPage | None] = relationship(back_populates="leads")


class RefreshRecommendation(Base):
    __tablename__ = "refresh_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    page_id: Mapped[str | None] = mapped_column(ForeignKey("landing_pages.id"))
    severity: Mapped[str] = mapped_column(String(40), default="medium")
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80))
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SeoIntegrationConnection(Base):
    __tablename__ = "seo_integration_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("business_profiles.id"))
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    property_ref: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="demo_mode")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    business: Mapped[BusinessProfile | None] = relationship(back_populates="seo_connections")


class SeoSearchMetric(Base):
    __tablename__ = "seo_search_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(ForeignKey("landing_pages.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(80), default="ALL")
    device: Mapped[str] = mapped_column(String(40), default="ALL")
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0)
    average_position: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(80), default="demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    page: Mapped[LandingPage] = relationship(back_populates="search_metrics")


class AnalyticsPageMetric(Base):
    __tablename__ = "analytics_page_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(ForeignKey("landing_pages.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, default=0)
    engaged_sessions: Mapped[int] = mapped_column(Integer, default=0)
    cta_clicks: Mapped[int] = mapped_column(Integer, default=0)
    form_starts: Mapped[int] = mapped_column(Integer, default=0)
    form_submits: Mapped[int] = mapped_column(Integer, default=0)
    scroll_75: Mapped[int] = mapped_column(Integer, default=0)
    traffic_source: Mapped[str] = mapped_column(String(120), default="organic")
    device: Mapped[str] = mapped_column(String(40), default="ALL")
    country: Mapped[str] = mapped_column(String(80), default="ALL")
    source: Mapped[str] = mapped_column(String(80), default="first_party")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    page: Mapped[LandingPage] = relationship(back_populates="analytics_metrics")


class PageEvent(Base):
    __tablename__ = "page_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str | None] = mapped_column(ForeignKey("landing_pages.id"))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(120))
    path: Mapped[str | None] = mapped_column(String(255))
    referrer: Mapped[str | None] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    page: Mapped[LandingPage | None] = relationship(back_populates="events")


class PageRefreshVersion(Base):
    __tablename__ = "page_refresh_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str] = mapped_column(ForeignKey("landing_pages.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    old_title: Mapped[str | None] = mapped_column(String(220))
    new_title: Mapped[str | None] = mapped_column(String(220))
    old_hero: Mapped[str | None] = mapped_column(Text)
    new_hero: Mapped[str | None] = mapped_column(Text)
    old_cta: Mapped[str | None] = mapped_column(String(160))
    new_cta: Mapped[str | None] = mapped_column(String(160))
    created_by: Mapped[str] = mapped_column(String(120), default="seo_refresh_agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    page: Mapped[LandingPage] = relationship(back_populates="refresh_versions")


class SeoRecommendationRun(Base):
    __tablename__ = "seo_recommendation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    run_type: Mapped[str] = mapped_column(String(80), default="weekly_refresh")
    pages_scored: Mapped[int] = mapped_column(Integer, default=0)
    recommendations_created: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="completed")
    source: Mapped[str] = mapped_column(String(80), default="first_party_and_demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    campaign: Mapped[Campaign | None] = relationship(back_populates="seo_runs")


class KeywordRankSnapshot(Base):
    __tablename__ = "keyword_rank_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    page_id: Mapped[str | None] = mapped_column(ForeignKey("landing_pages.id"))
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(120), default="global")
    rank_position: Mapped[float | None] = mapped_column(Float)
    search_engine: Mapped[str] = mapped_column(String(80), default="google")
    source: Mapped[str] = mapped_column(String(80), default="gsc")
    captured_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SitemapSubmission(Base):
    __tablename__ = "sitemap_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sitemap_url: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), default="google_search_console")
    status: Mapped[str] = mapped_column(String(40), default="pending")
    response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GrowthAgentExecution(Base):
    __tablename__ = "growth_agent_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_key: Mapped[str] = mapped_column(String(80), nullable=False)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("business_profiles.id"))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    status: Mapped[str] = mapped_column(String(40), default="completed")
    mode: Mapped[str] = mapped_column(String(80), default="demo_ready")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    recommendations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaidAdPlan(Base):
    __tablename__ = "paid_ad_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    business_id: Mapped[str | None] = mapped_column(ForeignKey("business_profiles.id"))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    target_region: Mapped[str] = mapped_column(String(120), default="India")
    daily_budget_micros: Mapped[int] = mapped_column(Integer, default=5000000)
    status: Mapped[str] = mapped_column(String(40), default="draft")
    approval_status: Mapped[str] = mapped_column(String(40), default="needs_review")
    google_campaign_resource_name: Mapped[str | None] = mapped_column(String(255))
    google_budget_resource_name: Mapped[str | None] = mapped_column(String(255))
    google_ad_group_resource_name: Mapped[str | None] = mapped_column(String(255))
    plan: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    push_response: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(120), default="paid_campaign_agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
