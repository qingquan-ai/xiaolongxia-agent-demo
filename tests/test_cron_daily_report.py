from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _set_cron_secret(value: str) -> None:
    object.__setattr__(settings, "cron_secret", value)


def test_cron_daily_report_allows_local_call_when_secret_missing(monkeypatch):
    client = TestClient(app)
    old_secret = getattr(settings, "cron_secret", "")
    _set_cron_secret("")
    called_sources = []
    monkeypatch.setattr(
        "app.main.generate_and_push_daily_report",
        lambda source: called_sources.append(source) or {"title": "ok"},
        raising=False,
    )

    try:
        response = client.post("/api/reports/daily")
    finally:
        _set_cron_secret(old_secret)

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "source": "cron_daily",
        "message": "daily report generated and pushed",
    }
    assert called_sources == ["cron_daily"]


def test_cron_daily_report_accepts_valid_secret(monkeypatch):
    client = TestClient(app)
    old_secret = getattr(settings, "cron_secret", "")
    _set_cron_secret("secret-for-test")
    called_sources = []
    monkeypatch.setattr(
        "app.main.generate_and_push_daily_report",
        lambda source: called_sources.append(source) or {"title": "ok"},
        raising=False,
    )

    try:
        response = client.post(
            "/api/reports/daily",
            headers={"X-Cron-Secret": "secret-for-test"},
        )
    finally:
        _set_cron_secret(old_secret)

    assert response.status_code == 200
    assert response.json()["source"] == "cron_daily"
    assert called_sources == ["cron_daily"]


def test_cron_daily_report_rejects_missing_secret_header(monkeypatch):
    client = TestClient(app)
    old_secret = getattr(settings, "cron_secret", "")
    _set_cron_secret("secret-for-test")
    called_sources = []
    monkeypatch.setattr(
        "app.main.generate_and_push_daily_report",
        lambda source: called_sources.append(source) or {"title": "ok"},
        raising=False,
    )

    try:
        response = client.post("/api/reports/daily")
    finally:
        _set_cron_secret(old_secret)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid cron secret"
    assert called_sources == []


def test_cron_daily_report_rejects_invalid_secret_header(monkeypatch):
    client = TestClient(app)
    old_secret = getattr(settings, "cron_secret", "")
    _set_cron_secret("secret-for-test")
    called_sources = []
    monkeypatch.setattr(
        "app.main.generate_and_push_daily_report",
        lambda source: called_sources.append(source) or {"title": "ok"},
        raising=False,
    )

    try:
        response = client.post(
            "/api/reports/daily",
            headers={"X-Cron-Secret": "wrong-secret"},
        )
    finally:
        _set_cron_secret(old_secret)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid cron secret"
    assert called_sources == []
