from fastapi.testclient import TestClient

from app.main import app


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
