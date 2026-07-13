from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean
from urllib.parse import quote, urljoin, urlparse

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
    GoogleAnalyticsEventMetric,
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
        range_start = datetime.combine(data.start_date, datetime.min.time())
        range_end = datetime.combine(data.end_date, datetime.min.time())
        records = 0

        db.query(SeoSearchMetric).filter(
            SeoSearchMetric.source.in_(["google_search_console", "google_search_console_query"]),
            SeoSearchMetric.date >= range_start,
            SeoSearchMetric.date <= range_end,
        ).delete()
        db.query(AnalyticsPageMetric).filter(
            AnalyticsPageMetric.source == "ga4",
            AnalyticsPageMetric.date >= range_start,
            AnalyticsPageMetric.date <= range_end,
        ).delete()
        db.query(GoogleAnalyticsEventMetric).filter(
            GoogleAnalyticsEventMetric.source == "ga4",
            GoogleAnalyticsEventMetric.date >= range_start,
            GoogleAnalyticsEventMetric.date <= range_end,
        ).delete()

        for row in data.search_rows:
            page = page_by_url.get(row.page_url.rstrip("/")) or page_by_path.get(urlparse(row.page_url).path)
            if not page:
                continue
            db.add(
                SeoSearchMetric(
                    page_id=page.id,
                    date=datetime.combine(row.date, datetime.min.time()),
                    query="",
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

        for row in data.search_query_rows:
            page = page_by_url.get(row.page_url.rstrip("/")) or page_by_path.get(urlparse(row.page_url).path)
            if not page:
                continue
            db.add(
                SeoSearchMetric(
                    page_id=page.id,
                    date=range_end,
                    query=row.query[:255],
                    country=row.country[:80],
                    device=row.device[:40],
                    impressions=row.impressions,
                    clicks=row.clicks,
                    ctr=row.ctr,
                    average_position=row.position,
                    source="google_search_console_query",
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
                    date=datetime.combine(row.date, datetime.min.time()),
                    sessions=row.sessions,
                    engaged_sessions=row.engaged_sessions,
                    cta_clicks=0,
                    form_starts=0,
                    form_submits=0,
                    scroll_75=0,
                    traffic_source=row.traffic_source[:120],
                    device=row.device[:40],
                    country=row.country[:80],
                    source="ga4",
                )
            )
            records += 1

        for row in data.analytics_event_rows:
            page = page_by_path.get(row.path.rstrip("/")) or page_by_path.get(row.path)
            if not page:
                continue
            db.add(
                GoogleAnalyticsEventMetric(
                    page_id=page.id,
                    date=datetime.combine(row.date, datetime.min.time()),
                    event_name=row.event_name[:120],
                    event_count=row.event_count,
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
                "query_rows": len(data.search_query_rows),
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
                "event_rows": len(data.analytics_event_rows),
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
            "search_console_query_rows": len(data.search_query_rows),
            "ga4_rows": len(data.analytics_rows),
            "ga4_event_rows": len(data.analytics_event_rows),
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
            indexed_pages=sum(
                1
                for score in scores
                if score.google_index_status["status"] == "google_data_detected"
            ),
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
            metric_sources={
                "indexed_pages": "Live Google Search Console",
                "organic_impressions": self._overview_source(scores, "impressions"),
                "organic_clicks": self._overview_source(scores, "clicks"),
                "ctr": self._overview_source(scores, "ctr"),
                "average_position": self._overview_source(scores, "average_position"),
                "sessions": self._overview_source(scores, "sessions"),
                "engaged_sessions": self._overview_source(scores, "engaged_sessions"),
                "leads": "App DB",
                "conversion_rate": self._overview_source(scores, "conversion_rate"),
            },
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
        sessions = sum(item.sessions for item in analytics)
        if not live_google and not sessions:
            sessions = page.visits
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
        business = page.campaign.business if page.campaign else None
        page_url = urljoin(settings.public_base_url.rstrip("/") + "/", f"p/{page.slug}")
        search_source = self._metric_source(
            {item.source for item in search}, fallback="Waiting for Google Search Console"
        )
        analytics_source = self._metric_source(
            {item.source for item in analytics},
            fallback="App DB" if page.visits else "Waiting for analytics events",
        )
        first_party_events = self._first_party_event_summary(db, page)
        google_index_status = self._google_index_status(
            db,
            settings,
            page,
            page_url=page_url,
            impressions=impressions,
            search_sources={item.source for item in search},
        )
        return SeoPageScore(
            page_id=page.id,
            business_id=business.id if business else None,
            business_name=business.name if business else None,
            slug=page.slug,
            title=page.title,
            url=page_url,
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
            metric_sources={
                "technical_score": "App calculation",
                "content_score": "App calculation",
                "search_score": search_source,
                "conversion_score": f"{analytics_source} + App DB",
                "overall_score": "App calculation",
                "impressions": search_source,
                "clicks": search_source,
                "ctr": search_source,
                "average_position": search_source,
                "sessions": analytics_source,
                "engaged_sessions": analytics_source,
                "leads": "App DB",
                "conversion_rate": f"{analytics_source} + App DB",
            },
            first_party_events=first_party_events,
            google_index_status=google_index_status,
        )

    def _first_party_event_summary(
        self, db: Session, page: LandingPage
    ) -> dict[str, object]:
        rows = (
            db.query(PageEvent.event_type, func.count(PageEvent.id), func.max(PageEvent.created_at))
            .filter(PageEvent.page_id == page.id)
            .group_by(PageEvent.event_type)
            .all()
        )
        counts = {event_type: int(count or 0) for event_type, count, _ in rows}
        last_event_at = max(
            (last_seen for _, _, last_seen in rows if last_seen is not None), default=None
        )
        leads = db.query(func.count(Lead.id)).filter(Lead.page_id == page.id).scalar() or 0
        return {
            "page_views": counts.get("page_view", 0),
            "cta_clicks": counts.get("cta_click", 0),
            "form_starts": counts.get("form_start", 0),
            "form_submits": counts.get("form_submit", 0),
            "leads": leads,
            "last_event_at": last_event_at,
            "metric_sources": {
                "page_views": "App events",
                "cta_clicks": "App events",
                "form_starts": "App events",
                "form_submits": "App events",
                "leads": "App DB",
            },
        }

    def _google_index_status(
        self,
        db: Session,
        settings: Settings,
        page: LandingPage,
        *,
        page_url: str,
        impressions: int,
        search_sources: set[str],
    ) -> dict[str, object]:
        connection = (
            db.query(SeoIntegrationConnection)
            .filter(SeoIntegrationConnection.provider == "google_search_console")
            .order_by(SeoIntegrationConnection.updated_at.desc())
            .first()
        )
        has_live_gsc = "google_search_console" in search_sources
        if has_live_gsc and impressions > 0:
            status = "google_data_detected"
            status_label = "Google performance data detected"
            source = "Live Google Search Console"
        elif connection and connection.status == "live_synced":
            status = "synced_no_impressions"
            status_label = "Synced; no Google impressions detected"
            source = "Live Google Search Console"
        elif connection and connection.status == "error":
            status = "sync_error"
            status_label = "Search Console sync needs attention"
            source = "Integration status"
        else:
            status = "awaiting_search_console_sync"
            status_label = "Awaiting live Search Console confirmation"
            source = "Integration status"

        property_ref = settings.google_search_console_site_url or settings.public_base_url
        inspect_url = (
            "https://search.google.com/search-console/inspect?"
            f"resource_id={quote(property_ref, safe='')}&id={quote(page_url, safe='')}"
        )
        return {
            "status": status,
            "status_label": status_label,
            "status_source": source,
            "search_console_inspect_url": inspect_url,
            "sitemap_url": f"{settings.public_base_url.rstrip('/')}/sitemap.xml",
            "in_sitemap": page.status == "published",
            "sitemap_source": "App-generated sitemap",
            "last_synced_at": connection.last_sync_at if connection else None,
            "last_sync_status": connection.status if connection else "not_synced",
            "manual_guidance": (
                "Open URL Inspection, run Test Live URL, then use Request Indexing. Google controls "
                "crawl and indexing timing; this portal does not promise or automate acceptance."
            ),
        }

    @staticmethod
    def _metric_source(sources: set[str], *, fallback: str) -> str:
        labels = {
            "google_search_console": "Live Google Search Console",
            "ga4": "Live GA4",
            "first_party": "App events",
            "demo_until_gsc_ga4_connected": "Demo fallback",
        }
        resolved = [labels.get(source, source.replace("_", " ").title()) for source in sorted(sources)]
        return " + ".join(resolved) if resolved else fallback

    @staticmethod
    def _overview_source(scores: list[SeoPageScore], key: str) -> str:
        sources = sorted({score.metric_sources[key] for score in scores})
        if not sources:
            return "Waiting for data"
        return sources[0] if len(sources) == 1 else "Mixed page sources"

    def google_reports(self, db: Session, settings: Settings) -> dict[str, object]:
        pages = db.query(LandingPage).filter(LandingPage.status == "published").all()
        gsc_connection = self._latest_connection(db, "google_search_console")
        ga4_connection = self._latest_connection(db, "ga4")
        start_date, end_date = self._report_range(gsc_connection or ga4_connection)
        start_at = datetime.combine(start_date, datetime.min.time())
        end_at = datetime.combine(end_date, datetime.max.time())

        search_rows = db.query(SeoSearchMetric).filter(
            SeoSearchMetric.source == "google_search_console",
            SeoSearchMetric.date >= start_at,
            SeoSearchMetric.date <= end_at,
        ).all()
        analytics_rows = db.query(AnalyticsPageMetric).filter(
            AnalyticsPageMetric.source == "ga4",
            AnalyticsPageMetric.date >= start_at,
            AnalyticsPageMetric.date <= end_at,
        ).all()
        event_rows = db.query(GoogleAnalyticsEventMetric).filter(
            GoogleAnalyticsEventMetric.source == "ga4",
            GoogleAnalyticsEventMetric.date >= start_at,
            GoogleAnalyticsEventMetric.date <= end_at,
        ).all()

        search_daily: dict[str, dict[str, float]] = {}
        search_pages: dict[str, dict[str, float]] = {}
        search_page_daily: dict[str, dict[str, dict[str, int]]] = {}
        for row in search_rows:
            day = row.date.date().isoformat()
            daily = search_daily.setdefault(day, {"impressions": 0, "clicks": 0, "position_total": 0, "position_weight": 0})
            page = search_pages.setdefault(row.page_id, {"impressions": 0, "clicks": 0, "position_total": 0, "position_weight": 0})
            for target in (daily, page):
                target["impressions"] += row.impressions
                target["clicks"] += row.clicks
                weight = max(row.impressions, 1)
                target["position_total"] += row.average_position * weight
                target["position_weight"] += weight
            page_day = search_page_daily.setdefault(row.page_id, {}).setdefault(
                day, {"impressions": 0, "clicks": 0}
            )
            page_day["impressions"] += row.impressions
            page_day["clicks"] += row.clicks

        page_sessions: dict[str, int] = {}
        for row in analytics_rows:
            page_sessions[row.page_id] = page_sessions.get(row.page_id, 0) + row.sessions
        page_events: dict[str, dict[str, int]] = {}
        event_totals: dict[str, int] = {}
        event_daily: dict[str, dict[str, int]] = {}
        event_page_daily: dict[str, dict[str, dict[str, int]]] = {}
        for row in event_rows:
            page_counts = page_events.setdefault(row.page_id, {})
            page_counts[row.event_name] = page_counts.get(row.event_name, 0) + row.event_count
            event_totals[row.event_name] = event_totals.get(row.event_name, 0) + row.event_count
            day_counts = event_daily.setdefault(row.date.date().isoformat(), {})
            day_counts[row.event_name] = day_counts.get(row.event_name, 0) + row.event_count
            page_day_counts = event_page_daily.setdefault(row.page_id, {}).setdefault(
                row.date.date().isoformat(), {}
            )
            page_day_counts[row.event_name] = page_day_counts.get(row.event_name, 0) + row.event_count

        lead_counts = dict(
            db.query(Lead.page_id, func.count(Lead.id))
            .filter(Lead.page_id.isnot(None))
            .group_by(Lead.page_id)
            .all()
        )
        qualified_counts = dict(
            db.query(Lead.page_id, func.count(Lead.id))
            .filter(Lead.page_id.isnot(None), Lead.status == "qualified")
            .group_by(Lead.page_id)
            .all()
        )

        report_pages = []
        for page in pages:
            search = search_pages.get(page.id, {})
            events = page_events.get(page.id, {})
            impressions = int(search.get("impressions", 0))
            clicks = int(search.get("clicks", 0))
            report_pages.append({
                "page_id": page.id,
                "title": page.title,
                "business": page.campaign.business.name if page.campaign and page.campaign.business else "Unknown company",
                "url": self._canonical_url(settings, page),
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round((clicks / impressions) * 100, 2) if impressions else 0,
                "average_position": round(search.get("position_total", 0) / search.get("position_weight", 1), 2) if search else 0,
                "sessions": page_sessions.get(page.id, 0),
                "events": events,
                "accepted_leads": int(lead_counts.get(page.id, 0)),
                "qualified_leads": int(qualified_counts.get(page.id, 0)),
                "search_daily": [
                    {"date": day, **counts}
                    for day, counts in sorted(search_page_daily.get(page.id, {}).items())
                ],
                "event_daily": [
                    {
                        "date": day,
                        "page_views": counts.get("page_view", 0),
                        "form_submits": counts.get("form_submit", 0),
                    }
                    for day, counts in sorted(event_page_daily.get(page.id, {}).items())
                ],
            })

        total_impressions = sum(int(row.impressions) for row in search_rows)
        total_clicks = sum(int(row.clicks) for row in search_rows)
        position_weight = sum(max(row.impressions, 1) for row in search_rows)
        weighted_position = sum(
            row.average_position * max(row.impressions, 1) for row in search_rows
        )
        return {
            "mode": self.integration_status(db, settings)["mode"],
            "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "last_synced_at": max(
                (item.last_sync_at for item in (gsc_connection, ga4_connection) if item and item.last_sync_at),
                default=None,
            ),
            "schedule": {
                "enabled": settings.google_sync_schedule_enabled,
                "time": settings.google_sync_schedule_time,
                "timezone": settings.google_sync_schedule_timezone,
                "label": f"Daily at {settings.google_sync_schedule_time} {settings.google_sync_schedule_timezone}",
            },
            "search_console": {
                "totals": {
                    "impressions": total_impressions,
                    "clicks": total_clicks,
                    "ctr": round((total_clicks / total_impressions) * 100, 2) if total_impressions else 0,
                    "average_position": round(weighted_position / position_weight, 2)
                    if position_weight
                    else 0,
                },
                "daily": [
                    {
                        "date": day,
                        "impressions": int(values["impressions"]),
                        "clicks": int(values["clicks"]),
                    }
                    for day, values in sorted(search_daily.items())
                ],
                "pages": sorted(report_pages, key=lambda item: (item["impressions"], item["clicks"]), reverse=True),
                "top_queries": self._top_queries(db),
                "privacy_note": "Page totals are authoritative. Low-volume queries may be withheld by Google.",
                "source": "Google Search Console",
            },
            "ga4": {
                "totals": {
                    "page_views": event_totals.get("page_view", 0),
                    "sessions": sum(page_sessions.values()),
                    "cta_clicks": event_totals.get("cta_click", 0),
                    "form_starts": event_totals.get("form_start", 0),
                    "form_submits": event_totals.get("form_submit", 0),
                },
                "daily": [
                    {
                        "date": day,
                        "page_views": values.get("page_view", 0),
                        "form_submits": values.get("form_submit", 0),
                    }
                    for day, values in sorted(event_daily.items())
                ],
                "events": [
                    {"event_name": name, "event_count": count, "source": "Google Analytics"}
                    for name, count in sorted(event_totals.items(), key=lambda item: item[1], reverse=True)
                ],
                "pages": report_pages,
                "source": "Google Analytics",
            },
        }

    @staticmethod
    def _latest_connection(db: Session, provider: str) -> SeoIntegrationConnection | None:
        return db.query(SeoIntegrationConnection).filter(
            SeoIntegrationConnection.provider == provider
        ).order_by(SeoIntegrationConnection.updated_at.desc()).first()

    @staticmethod
    def _report_range(connection: SeoIntegrationConnection | None) -> tuple[date, date]:
        fallback_end = datetime.now().date() - timedelta(days=2)
        fallback_start = fallback_end - timedelta(days=27)
        if not connection or not connection.config:
            return fallback_start, fallback_end
        try:
            return (
                date.fromisoformat(str(connection.config["start_date"])),
                date.fromisoformat(str(connection.config["end_date"])),
            )
        except (KeyError, TypeError, ValueError):
            return fallback_start, fallback_end

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
            SeoSearchMetric.source,
        )
        if self._live_google_synced(db):
            query = query.filter(SeoSearchMetric.source == "google_search_console_query")
        rows = (
            query.group_by(SeoSearchMetric.query, SeoSearchMetric.source)
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
                "source": self._metric_source({row[4]}, fallback="Waiting for data"),
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
