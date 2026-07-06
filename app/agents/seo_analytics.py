from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from urllib.parse import urljoin, urlparse

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import Settings
from app.integrations.google_marketing import (
    GoogleMarketingData,
    GoogleMarketingIntegration,
    GoogleMarketingIntegrationError,
)
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
        required = {
            "ga4_property_id": configured["ga4_property_id"],
            "search_console_site_url": configured["search_console_site_url"],
            "google_service_account": configured["google_service_account"],
        }
        connections = db.query(SeoIntegrationConnection).order_by(
            SeoIntegrationConnection.created_at.desc()
        ).all()
        connection_statuses = {item.provider: item.status for item in connections}
        if connection_statuses and any(status == "error" for status in connection_statuses.values()):
            mode = "google_sync_error_fallback"
        elif (
            all(required.values())
            and connection_statuses.get("google_search_console") == "live_synced"
            and connection_statuses.get("ga4") == "live_synced"
        ):
            mode = "live_google_integrated"
        elif all(required.values()):
            mode = "google_credentials_configured"
        else:
            mode = "demo_with_first_party_events"
        return {
            "mode": mode,
            "configured": configured,
            "required_for_live": required,
            "setup_steps": self._setup_steps(settings),
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
        google = GoogleMarketingIntegration(settings)
        google_error: str | None = None
        if google.is_configured:
            try:
                result = self._sync_live_google_metrics(db, settings, google.fetch())
                record_audit(
                    db,
                    actor=self.name,
                    action="seo_metrics_synced",
                    entity_type="seo_metrics",
                    metadata=result,
                )
                db.commit()
                return result
            except GoogleMarketingIntegrationError as exc:
                google_error = str(exc)
                self._upsert_connection(
                    db,
                    provider="google_search_console",
                    property_ref=settings.google_search_console_site_url or "not_configured",
                    status="error",
                    config={"message": google_error},
                )
                self._upsert_connection(
                    db,
                    provider="ga4",
                    property_ref=settings.ga4_property_id or settings.ga4_measurement_id or "not_configured",
                    status="error",
                    config={"message": google_error},
                )
                record_audit(
                    db,
                    actor=self.name,
                    action="seo_metrics_sync_failed",
                    entity_type="seo_metrics",
                    metadata={"message": google_error, "fallback": "demo_with_first_party_events"},
                )
                db.commit()

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
            status="error"
            if google_error
            else ("ready_for_credentials" if not google.is_configured else "configured_without_live_data"),
            config={"message": google_error} if google_error else {"required": self._setup_steps(settings)},
        )
        self._upsert_connection(
            db,
            provider="ga4",
            property_ref=settings.ga4_property_id or settings.ga4_measurement_id or "not_configured",
            status="error"
            if google_error
            else (
                "ready_for_credentials"
                if not (settings.ga4_property_id and settings.google_service_account_json)
                else "configured_without_live_data"
            ),
            config={"message": google_error} if google_error else {"required": self._setup_steps(settings)},
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
            "fallback_reason": google_error,
        }

    def _sync_live_google_metrics(
        self,
        db: Session,
        settings: Settings,
        data: GoogleMarketingData,
    ) -> dict[str, object]:
        pages = db.query(LandingPage).filter(LandingPage.status == "published").all()
        page_by_url = {self._canonical_url(settings, page): page for page in pages}
        page_by_path = {f"/p/{page.slug}": page for page in pages}
        metric_date = datetime.combine(data.end_date, datetime.min.time())
        records = 0

        db.query(SeoSearchMetric).filter(
            SeoSearchMetric.date == metric_date,
            SeoSearchMetric.source == "google_search_console",
        ).delete()
        db.query(AnalyticsPageMetric).filter(
            AnalyticsPageMetric.date == metric_date,
            AnalyticsPageMetric.source == "ga4",
        ).delete()

        for row in data.search_rows:
            page = page_by_url.get(row.page_url.rstrip("/")) or page_by_path.get(urlparse(row.page_url).path)
            if not page:
                continue
            db.add(
                SeoSearchMetric(
                    page_id=page.id,
                    date=metric_date,
                    query=row.query[:255],
                    country=row.country[:80],
                    device=row.device[:40],
                    impressions=row.impressions,
                    clicks=row.clicks,
                    ctr=row.ctr,
                    average_position=row.position,
                    source="google_search_console",
                )
            )
            records += 1

        for row in data.analytics_rows:
            page = page_by_path.get(row.path.rstrip("/")) or page_by_path.get(row.path)
            if not page:
                continue
            db.add(
                AnalyticsPageMetric(
                    page_id=page.id,
                    date=metric_date,
                    sessions=row.sessions,
                    engaged_sessions=row.engaged_sessions,
                    cta_clicks=0,
                    form_starts=0,
                    form_submits=row.conversions,
                    scroll_75=0,
                    traffic_source=row.traffic_source[:120],
                    device=row.device[:40],
                    country=row.country[:80],
                    source="ga4",
                )
            )
            records += 1

        self._upsert_connection(
            db,
            provider="google_search_console",
            property_ref=settings.google_search_console_site_url or settings.public_base_url,
            status="live_synced",
            config={
                "start_date": data.start_date.isoformat(),
                "end_date": data.end_date.isoformat(),
                "rows": len(data.search_rows),
            },
        )
        self._upsert_connection(
            db,
            provider="ga4",
            property_ref=settings.ga4_property_id or settings.ga4_measurement_id or "not_configured",
            status="live_synced",
            config={
                "start_date": data.start_date.isoformat(),
                "end_date": data.end_date.isoformat(),
                "rows": len(data.analytics_rows),
            },
        )
        return {
            "pages_synced": len(pages),
            "records_written": records,
            "mode": "live_google_integrated",
            "date_range": {
                "start": data.start_date.isoformat(),
                "end": data.end_date.isoformat(),
            },
            "search_console_rows": len(data.search_rows),
            "ga4_rows": len(data.analytics_rows),
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
        live_google = self._live_google_synced(db)
        search_query = db.query(SeoSearchMetric).filter(SeoSearchMetric.page_id == page.id)
        analytics_query = db.query(AnalyticsPageMetric).filter(AnalyticsPageMetric.page_id == page.id)
        if live_google:
            search_query = search_query.filter(SeoSearchMetric.source == "google_search_console")
            analytics_query = analytics_query.filter(AnalyticsPageMetric.source == "ga4")
        search = search_query.all()
        analytics = analytics_query.all()
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
        self,
        db: Session,
        *,
        provider: str,
        property_ref: str,
        status: str,
        config: dict[str, object] | None = None,
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
        connection.config = config or {}
        connection.last_sync_at = datetime.now()

    def _setup_steps(self, settings: Settings) -> list[dict[str, object]]:
        return [
            {
                "key": "ga4_property_id",
                "label": "Set GA4 property id",
                "complete": bool(settings.ga4_property_id),
                "value": settings.ga4_property_id or "",
            },
            {
                "key": "ga4_measurement_id",
                "label": "Set GA4 web measurement id for browser events",
                "complete": bool(settings.ga4_measurement_id),
                "value": settings.ga4_measurement_id or "",
            },
            {
                "key": "google_search_console_site_url",
                "label": "Set Search Console property URL",
                "complete": bool(settings.google_search_console_site_url),
                "value": settings.google_search_console_site_url or "",
            },
            {
                "key": "google_service_account_json",
                "label": "Attach service account JSON with GA4 and Search Console read access",
                "complete": bool(settings.google_service_account_json),
                "value": "configured" if settings.google_service_account_json else "",
            },
        ]

    def _canonical_url(self, settings: Settings, page: LandingPage) -> str:
        return urljoin(settings.public_base_url.rstrip("/") + "/", f"p/{page.slug}").rstrip("/")

    def _live_google_synced(self, db: Session) -> bool:
        statuses = {
            item.provider: item.status
            for item in db.query(SeoIntegrationConnection).filter(
                SeoIntegrationConnection.provider.in_(["google_search_console", "ga4"])
            )
        }
        return (
            statuses.get("google_search_console") == "live_synced"
            and statuses.get("ga4") == "live_synced"
        )

    def _top_queries(self, db: Session) -> list[dict[str, object]]:
        query = db.query(
            SeoSearchMetric.query,
            func.sum(SeoSearchMetric.impressions),
            func.sum(SeoSearchMetric.clicks),
            func.avg(SeoSearchMetric.average_position),
        )
        if self._live_google_synced(db):
            query = query.filter(SeoSearchMetric.source == "google_search_console")
        rows = (
            query.group_by(SeoSearchMetric.query)
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
