import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OPENAI_ENABLED", "false")
    monkeypatch.setenv("SSM_ENABLED", "false")

    from app.core.config import get_settings
    from app.core import database

    get_settings.cache_clear()
    database.settings = get_settings()
    database.engine.dispose()
    database.engine = database.create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    database.SessionLocal.configure(bind=database.engine)

    from app.main import create_app

    app = create_app()
    return TestClient(app)
