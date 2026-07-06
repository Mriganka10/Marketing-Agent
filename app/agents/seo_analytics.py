from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from urllib.parse import urljoin

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import Settings
from app.models.entities import (
    AnalyticsPageMetric,
    Campaign,
    LandingPage,
    Lead,
    PageEvent,
    SeoIntegrationConnection,
    SeoRecommendationRun,
    SeoSearchMetric,
)
from app.models.schemas import PageEventCreate, SeoOverview, SeoPageScore


@dataclass(frozen=True)
class PageMetricBundle:
    impressions: int
    clicks: int
    ctr: float
    average_position: float
    sessions: int
    engaged_sessions: int
    cta_clicks: int
    form_starts: int
    form_submits: int
    top_query: str
    source: str


class SeoAnalyticsAgent:
    name = "seo_analytics_agent"

    def integration_status(self, db: Session, settings: Settings) -> dict[str, object]:
        configured = {
            "domain": settings.public_base_url,
            "ga4_measurement_id": bool(settings.ga4_measurement_id),
            "ga4_property_id": bool(settings.ga4_property_id),
            "search_console_site_url": bool(settings.google_search_console_site_url),
            "google_service_account": bool(settings.google_service_account_json),
        }
        mode = "live_ready" if all(configured.values()) else "demo_with_first_party_events"
        connections = db.query(SeoIntegrationConnection).order_by(
            SeoIntegrationConnection.created_at.desc()
        ).all()
        return {
            "mode": mode,
            "configured": configured,
            "connections": [
                {
                    "provider": item.provider,
                    "status": item.status,
                    "property_ref": item.property_ref,
                    "last_sync_at": item.last_sync_at,
                }
                for item in connections
            ],
        }

    def record_event(
        self,
        db: Session,
        payload: PageEventCreate,
        *,
        user_agent: str | None = None,
    ) -> PageEvent:
        event = PageEvent(
            page_id=payload.page_id,
            campaign_id=payload.campaign_id,
            event_type=payload.event_type,
            session_id=payload.session_id,
            path=payload.path,
            referrer=payload.referrer,
            user_agent=user_agent,
            event_metadata=payload.event_metadata,
        )
        db.add(event)
        self._upsert_daily_first_party_metric(db, payload)
        db.commit()
        db.refresh(event)
        return event

    def sync_metrics(self, db: Session, settings: Settings) -> dict[str, object]:
        pages = db.query(LandingPage).filter(LandingPage.status == "published").all()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        created = 0
        for page in pages:
            bundle = self._demo_bundle(page)
            self._replace_search_metric(db, page, today, bundle)
            self._replace_analytics_metric(db, page, today, bundle)
            created += 2
        self._upsert_connection(
            db,
            provider="google_search_console",
            property_ref=settings.google_search_console_site_url or settings.public_base_url,
            status="ready_for_credentials" if not settings.google_service_account_json else "configured",
        )
        self._upsert_connection(
            db,
            provider="ga4",
            property_ref=settings.ga4_property_id or settings.ga4_measurement_id or "not_configured",
            status="ready_for_credentials"
            if not (settings.ga4_property_id and settings.google_service_account_json)
            else "configured",
        )
        record_audit(
            db,
            actor=self.name,
            action="seo_metrics_synced",
            entity_type="seo_metrics",
            metadata={
                "pages": len(pages),
                "records": created,
                "mode": self.integration_status(db, settings)["mode"],
            },
        )
        db.commit()
        return {
            "pages_synced": len(pages),
            "records_written": created,
            "mode": self.integration_status(db, settings)["mode"],
        }

    def overview(self, db: Session, settings: Settings) -> SeoOverview:
        pages = db.query(LandingPage).filter(LandingPage.status == "published").all()
        scores = [self.score_page(db, page, settings) for page in pages]
        impressions = sum(score.impressions for score in scores)
        clicks = sum(score.clicks for score in scores)
        sessions = sum(score.sessions for score in scores)
        engaged_sessions = sum(score.engaged_sessions for score in scores)
        leads = sum(score.leads for score in scores)
        top_queries = self._top_queries(db)
        return SeoOverview(
            pages_published=len(pages),
            indexed_pages=sum(1 for score in scores if score.impressions > 0),
            organic_impressions=impressions,
            organic_clicks=clicks,
            ctr=round((clicks / impressions) * 100, 2) if impressions else 0,
            average_position=round(mean([score.average_position for score in scores]), 2)
            if scores
            else 0,
            sessions=sessions,
            engaged_sessions=engaged_sessions,
            leads=leads,
            conversion_rate=round((leads / sessions) * 100, 2) if sessions else 0,
            pages_needing_refresh=sum(1 for score in scores if score.overall_score < 70),
            top_queries=top_queries,
            integration_status=self.integration_status(db, settings),
            page_scores=scores,
        )

    def score_page(self, db: Session, page: LandingPage, settings: Settings) -> SeoPageScore:
        search = db.query(SeoSearchMetric).filter(SeoSearchMetric.page_id == page.id).all()
        analytics = db.query(AnalyticsPageMetric).filter(AnalyticsPageMetric.page_id == page.id).all()
        leads = db.query(func.count(Lead.id)).filter(Lead.page_id == page.id).scalar() or 0
        impressions = sum(item.impressions for item in search)
        clicks = sum(item.clicks for item in search)
        sessions = sum(item.sessions for item in analytics) or page.visits
        engaged_sessions = sum(item.engaged_sessions for item in analytics)
        ctr = (clicks / impressions) * 100 if impressions else 0
        average_position = mean([item.average_position for item in search]) if search else 0
        conversion_rate = (leads / sessions) * 100 if sessions else 0
        technical_score = self._technical_score(page, settings)
        content_score = self._content_score(page)
        search_score = self._search_score(impressions, ctr, average_position)
        conversion_score = self._conversion_score(sessions, conversion_rate, engaged_sessions)
        overall = round(
            technical_score * 0.25
            + content_score * 0.25
            + search_score * 0.25
            + conversion_score * 0.25,
            2,
        )
        diagnosis, action = self._diagnose(
            impressions=impressions,
            clicks=clicks,
            ctr=ctr,
            average_position=average_position,
            sessions=sessions,
            conversion_rate=conversion_rate,
        )
        return SeoPageScore(
            page_id=page.id,
            slug=page.slug,
            title=page.title,
            url=urljoin(settings.public_base_url.rstrip("/") + "/", f"p/{page.slug}"),
            technical_score=technical_score,
            content_score=content_score,
            search_score=search_score,
            conversion_score=conversion_score,
            overall_score=overall,
            impressions=impressions,
            clicks=clicks,
            ctr=round(ctr, 2),
            average_position=round(average_position, 2),
            sessions=sessions,
            engaged_sessions=engaged_sessions,
            leads=leads,
            conversion_rate=round(conversion_rate, 2),
            diagnosis=diagnosis,
            next_action=action,
        )

    def record_recommendation_run(
        self, db: Session, campaign: Campaign | None, *, pages: int, recommendations: int
    ) -> None:
        db.add(
            SeoRecommendationRun(
                campaign_id=campaign.id if campaign else None,
                pages_scored=pages,
                recommendations_created=recommendations,
            )
        )

    def _upsert_daily_first_party_metric(self, db: Session, payload: PageEventCreate) -> None:
        if not payload.page_id:
            return
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        metric = (
            db.query(AnalyticsPageMetric)
            .filter(
                AnalyticsPageMetric.page_id == payload.page_id,
                AnalyticsPageMetric.date == today,
                AnalyticsPageMetric.source == "first_party",
            )
            .first()
        )
        if not metric:
            metric = AnalyticsPageMetric(page_id=payload.page_id, date=today, source="first_party")
            db.add(metric)
        if payload.event_type == "page_view":
            metric.sessions = (metric.sessions or 0) + 1
        elif payload.event_type == "cta_click":
            metric.cta_clicks = (metric.cta_clicks or 0) + 1
            metric.engaged_sessions = (metric.engaged_sessions or 0) + 1
        elif payload.event_type == "form_start":
            metric.form_starts = (metric.form_starts or 0) + 1
            metric.engaged_sessions = (metric.engaged_sessions or 0) + 1
        elif payload.event_type == "form_submit":
            metric.form_submits = (metric.form_submits or 0) + 1
            metric.engaged_sessions = (metric.engaged_sessions or 0) + 1
        elif payload.event_type == "scroll_75":
            metric.scroll_75 = (metric.scroll_75 or 0) + 1
            metric.engaged_sessions = (metric.engaged_sessions or 0) + 1

    def _demo_bundle(self, page: LandingPage) -> PageMetricBundle:
        seed = sum(ord(ch) for ch in page.slug)
        impressions = max(80, page.visits * 18 + 120 + seed % 420)
        clicks = max(4, int(impressions * (0.025 + (seed % 35) / 1000)))
        sessions = max(page.visits, clicks + seed % 18)
        engaged = max(0, min(sessions, int(sessions * (0.45 + (seed % 25) / 100))))
        cta = max(page.conversions, int(sessions * (0.08 + (seed % 10) / 100)))
        starts = max(page.conversions, int(cta * 0.75))
        submits = max(page.conversions, int(starts * 0.42))
        position = round(4 + (seed % 260) / 10, 2)
        keywords = page.seo.get("keywords") if page.seo else None
        if isinstance(keywords, list) and keywords:
            query = str(keywords[0])
        elif isinstance(keywords, str) and keywords.strip():
            query = keywords.split(",")[0].strip()
        else:
            query = page.title
        return PageMetricBundle(
            impressions=impressions,
            clicks=clicks,
            ctr=round(clicks / impressions, 4),
            average_position=position,
            sessions=sessions,
            engaged_sessions=engaged,
            cta_clicks=cta,
            form_starts=starts,
            form_submits=submits,
            top_query=query.lower(),
            source="demo_until_gsc_ga4_connected",
        )

    def _replace_search_metric(
        self, db: Session, page: LandingPage, date: datetime, bundle: PageMetricBundle
    ) -> None:
        db.query(SeoSearchMetric).filter(
            SeoSearchMetric.page_id == page.id,
            SeoSearchMetric.date == date,
            SeoSearchMetric.source == bundle.source,
        ).delete()
        db.add(
            SeoSearchMetric(
                page_id=page.id,
                date=date,
                query=bundle.top_query,
                country="IN",
                device="ALL",
                impressions=bundle.impressions,
                clicks=bundle.clicks,
                ctr=bundle.ctr,
                average_position=bundle.average_position,
                source=bundle.source,
            )
        )

    def _replace_analytics_metric(
        self, db: Session, page: LandingPage, date: datetime, bundle: PageMetricBundle
    ) -> None:
        db.query(AnalyticsPageMetric).filter(
            AnalyticsPageMetric.page_id == page.id,
            AnalyticsPageMetric.date == date,
            AnalyticsPageMetric.source == bundle.source,
        ).delete()
        db.add(
            AnalyticsPageMetric(
                page_id=page.id,
                date=date,
                sessions=bundle.sessions,
                engaged_sessions=bundle.engaged_sessions,
                cta_clicks=bundle.cta_clicks,
                form_starts=bundle.form_starts,
                form_submits=bundle.form_submits,
                scroll_75=max(0, bundle.engaged_sessions - bundle.form_starts),
                traffic_source="organic",
                device="ALL",
                country="IN",
                source=bundle.source,
            )
        )

    def _upsert_connection(
        self, db: Session, *, provider: str, property_ref: str, status: str
    ) -> None:
        connection = (
            db.query(SeoIntegrationConnection)
            .filter(SeoIntegrationConnection.provider == provider)
            .first()
        )
        if not connection:
            connection = SeoIntegrationConnection(provider=provider)
            db.add(connection)
        connection.property_ref = property_ref
        connection.status = status
        connection.last_sync_at = datetime.now()

    def _top_queries(self, db: Session) -> list[dict[str, object]]:
        rows = (
            db.query(
                SeoSearchMetric.query,
                func.sum(SeoSearchMetric.impressions),
                func.sum(SeoSearchMetric.clicks),
                func.avg(SeoSearchMetric.average_position),
            )
            .group_by(SeoSearchMetric.query)
            .order_by(func.sum(SeoSearchMetric.clicks).desc())
            .limit(8)
            .all()
        )
        return [
            {
                "query": row[0],
                "impressions": int(row[1] or 0),
                "clicks": int(row[2] or 0),
                "average_position": round(float(row[3] or 0), 2),
            }
            for row in rows
        ]

    def _technical_score(self, page: LandingPage, settings: Settings) -> float:
        score = 55
        if settings.public_base_url.startswith("https://"):
            score += 15
        if page.seo.get("description"):
            score += 10
        if page.seo.get("keywords"):
            score += 8
        if page.status == "published":
            score += 7
        if page.sections and len(page.sections) >= 3:
            score += 5
        return min(100, score)

    def _content_score(self, page: LandingPage) -> float:
        score = 45
        word_count = len(" ".join([page.title, page.hero, *(s.get("body", "") for s in page.sections)]).split())
        if word_count >= 180:
            score += 20
        elif word_count >= 90:
            score += 12
        if len(page.sections) >= 3:
            score += 15
        if page.cta:
            score += 10
        if page.seo.get("keywords"):
            score += 10
        return min(100, score)

    def _search_score(self, impressions: int, ctr: float, position: float) -> float:
        score = 35
        if impressions >= 1000:
            score += 20
        elif impressions >= 250:
            score += 12
        if ctr >= 5:
            score += 20
        elif ctr >= 2:
            score += 10
        if 0 < position <= 5:
            score += 25
        elif 0 < position <= 15:
            score += 15
        return min(100, score)

    def _conversion_score(self, sessions: int, conversion_rate: float, engaged: int) -> float:
        score = 35
        if sessions >= 100:
            score += 12
        elif sessions >= 25:
            score += 8
        engagement_rate = (engaged / sessions) * 100 if sessions else 0
        if engagement_rate >= 55:
            score += 18
        elif engagement_rate >= 30:
            score += 10
        if conversion_rate >= 6:
            score += 30
        elif conversion_rate >= 3:
            score += 20
        elif conversion_rate > 0:
            score += 8
        return min(100, score)

    def _diagnose(
        self,
        *,
        impressions: int,
        clicks: int,
        ctr: float,
        average_position: float,
        sessions: int,
        conversion_rate: float,
    ) -> tuple[str, str]:
        if impressions < 100:
            return (
                "Low search discovery",
                "Improve keyword targeting, internal links, sitemap coverage, and content depth.",
            )
        if impressions >= 300 and ctr < 2:
            return (
                "High impressions but low CTR",
                "Rewrite title, meta description, and schema to make the search result more compelling.",
            )
        if clicks >= 20 and sessions >= 20 and conversion_rate < 3:
            return (
                "Traffic is arriving but not converting",
                "Refresh hero, CTA, proof, lead magnet, and form friction.",
            )
        if average_position and average_position > 15:
            return (
                "Ranking below first-page threshold",
                "Expand page depth, strengthen semantic coverage, and add authority links.",
            )
        return (
            "Page is working",
            "Create variants by keyword, geography, persona, or industry to scale the winning pattern.",
        )
