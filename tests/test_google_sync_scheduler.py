from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.core.google_sync_scheduler import next_google_sync_at


def test_google_sync_schedule_uses_configured_ist_time():
    settings = Settings(
        google_sync_schedule_time="08:30",
        google_sync_schedule_timezone="Asia/Kolkata",
    )
    timezone = ZoneInfo("Asia/Kolkata")

    same_day = next_google_sync_at(
        settings,
        now=datetime(2026, 7, 13, 7, 45, tzinfo=timezone),
    )
    next_day = next_google_sync_at(
        settings,
        now=datetime(2026, 7, 13, 8, 30, tzinfo=timezone),
    )

    assert same_day == datetime(2026, 7, 13, 8, 30, tzinfo=timezone)
    assert next_day == datetime(2026, 7, 14, 8, 30, tzinfo=timezone)


def test_database_url_uses_installed_psycopg_driver():
    settings = Settings(database_url="postgresql://user:pass@db.example/marketing")
    assert settings.database_url == "postgresql+psycopg://user:pass@db.example/marketing"
