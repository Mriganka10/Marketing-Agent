import json

import pytest

from app import worker


def test_worker_runs_google_sync(monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "run_google_sync_once", calls.append)
    monkeypatch.setattr(worker, "get_settings", lambda: "settings")
    worker.process_message(json.dumps({"action": "google_metrics_sync"}))
    assert calls == ["settings"]


def test_worker_rejects_unknown_action():
    with pytest.raises(ValueError, match="Unsupported"):
        worker.process_message(json.dumps({"action": "unknown"}))
