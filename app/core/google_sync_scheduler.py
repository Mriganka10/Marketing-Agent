from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.agents.seo_analytics import SeoAnalyticsAgent
from app.core.audit import record_audit
from app.core.config import Settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


def next_google_sync_at(settings: Settings, *, now: datetime | None = None) -> datetime:
    timezone = ZoneInfo(settings.google_sync_schedule_timezone)
    current = now.astimezone(timezone) if now else datetime.now(timezone)
    hour, minute = (int(part) for part in settings.google_sync_schedule_time.split(":", 1))
    target = datetime.combine(current.date(), time(hour, minute), tzinfo=timezone)
    if target <= current:
        target += timedelta(days=1)
    return target


async def run_google_sync_schedule(settings: Settings) -> None:
    if not settings.google_sync_schedule_enabled or settings.environment != "production":
        return
    while True:
        target = next_google_sync_at(settings)
        delay = max(1, (target - datetime.now(target.tzinfo)).total_seconds())
        logger.info("Next automatic Google metrics sync scheduled for %s", target.isoformat())
        await asyncio.sleep(delay)
        await asyncio.to_thread(_run_sync, settings)


def _run_sync(settings: Settings) -> None:
    with SessionLocal() as db:
        try:
            result = SeoAnalyticsAgent().sync_metrics(db, settings)
            record_audit(
                db,
                actor="google_sync_scheduler",
                action="scheduled_google_sync_completed",
                entity_type="seo_metrics",
                metadata=result,
            )
        except Exception as exc:  # pragma: no cover - guarded production background loop
            logger.exception("Scheduled Google metrics sync failed")
            record_audit(
                db,
                actor="google_sync_scheduler",
                action="scheduled_google_sync_failed",
                entity_type="seo_metrics",
                metadata={"error_type": type(exc).__name__},
            )
