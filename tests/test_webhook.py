from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _set_feishu_verification_token(value: str) -> None:
    object.__setattr__(settings, "feishu_verification_token", value)


def test_home_health_and_docs_are_accessible():
    client = TestClient(app)

    assert client.get("/").status_code == 200
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200


def test_feishu_webhook_generates_daily_report():
    client = TestClient(app)

    response = client.post(
        "/api/webhook/feishu",
        json={
            "event_id": "demo-001",
            "sender": "运营小王",
            "chat_id": "demo-chat",
            "text": "生成今日小龙虾运营日报",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["received"] is True
    assert body["intent"] == "daily_report"
    assert "已生成今日运营日报" in body["reply"]
    assert body["result"]["title"] == "今日小龙虾运营日报"


def test_feishu_event_challenge_validates_token():
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    try:
        response = client.post(
            "/api/feishu/events",
            json={
                "challenge": "challenge-value",
                "token": "test-token",
            },
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-value"}


def test_feishu_event_rejects_invalid_token():
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    try:
        response = client.post(
            "/api/feishu/events",
            json={
                "challenge": "challenge-value",
                "token": "wrong-token",
            },
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 403


def test_feishu_event_generates_daily_report(monkeypatch):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )

    try:
        response = client.post(
            "/api/feishu/events",
            json={
                "schema": "2.0",
                "header": {
                    "event_id": "event-daily-report-001",
                    "event_type": "im.message.receive_v1",
                    "token": "test-token",
                },
                "event": {
                    "message": {
                        "message_type": "text",
                        "content": "{\"text\":\"@机器人 生成今日日报\"}",
                    },
                },
            },
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert len(sent_messages) == 1


def test_feishu_event_skips_duplicate_event(monkeypatch):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    body = {
        "schema": "2.0",
        "header": {
            "event_id": "event-daily-report-duplicate-001",
            "event_type": "im.message.receive_v1",
            "token": "test-token",
        },
        "event": {
            "message": {
                "message_type": "text",
                "content": "{\"text\":\"生成今日日报\"}",
            },
        },
    }

    try:
        first_response = client.post("/api/feishu/events", json=body)
        second_response = client.post("/api/feishu/events", json=body)
    finally:
        _set_feishu_verification_token(old_token)

    assert first_response.status_code == 200
    assert first_response.json() == {"ok": True, "handled": True}
    assert second_response.status_code == 200
    assert second_response.json() == {"ok": True, "duplicate": True}
    assert len(sent_messages) == 1
