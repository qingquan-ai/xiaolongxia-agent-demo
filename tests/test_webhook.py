import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


HELP_MESSAGE_EXPECTED = (
    "我可以帮你生成小龙虾门店经营日报。\n\n"
    "你可以这样使用我：\n"
    "1. 在群里 @我，发送「生成今日日报」\n"
    "2. 我会自动读取飞书多维表格里的订单、评论和竞品数据\n"
    "3. 然后生成经营概况、舆情风险、竞品观察和明日行动建议\n"
    "4. 最后把日报推送回这个飞书群\n\n"
    "目前我主要支持：生成今日日报。"
)
UNKNOWN_MESSAGE_EXPECTED = (
    "我暂时主要支持「生成今日日报」。\n\n"
    "你可以在群里 @我 发送：\n"
    "生成今日日报"
)


def _set_feishu_verification_token(value: str) -> None:
    object.__setattr__(settings, "feishu_verification_token", value)


def _assert_help_message(message: str) -> None:
    assert message == HELP_MESSAGE_EXPECTED


def _post_feishu_text(client: TestClient, event_id: str, text: str):
    return client.post(
        "/api/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_id": event_id,
                "event_type": "im.message.receive_v1",
                "token": "test-token",
            },
            "event": {
                "message": {
                    "message_type": "text",
                    "content": f"{{\"text\":\"{text}\"}}",
                },
            },
        },
    )


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
    assert set(body) == {"received", "intent", "reply", "result"}
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


def test_feishu_event_sends_latest_report_without_generating(monkeypatch):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("latest report command must not generate report")
        ),
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.load_latest_report_cache",
        lambda: {
            "report": {
                "agent": "写日报虾",
                "title": "今日小龙虾运营日报",
                "markdown": "最新日报正文",
            }
        },
        raising=False,
    )

    try:
        response = client.post(
            "/api/feishu/events",
            json={
                "schema": "2.0",
                "header": {
                    "event_id": "event-latest-report-001",
                    "event_type": "im.message.receive_v1",
                    "token": "test-token",
                },
                "event": {
                    "message": {
                        "message_type": "text",
                        "content": "{\"text\":\"查看最新日报\"}",
                    },
                },
            },
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert sent_messages == ["最新日报正文"]


def test_feishu_event_sends_empty_message_when_latest_report_missing(monkeypatch):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("missing latest report command must not generate report")
        ),
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.load_latest_report_cache",
        lambda: None,
        raising=False,
    )

    try:
        response = client.post(
            "/api/feishu/events",
            json={
                "schema": "2.0",
                "header": {
                    "event_id": "event-latest-report-missing-001",
                    "event_type": "im.message.receive_v1",
                    "token": "test-token",
                },
                "event": {
                    "message": {
                        "message_type": "text",
                        "content": "{\"text\":\"查看最新日报\"}",
                    },
                },
            },
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert sent_messages == ["暂无日报，请先发送‘生成今日日报’。"]


def test_feishu_event_sends_help_commands(monkeypatch):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("help command must not generate report")
        ),
    )

    try:
        response = client.post(
            "/api/feishu/events",
            json={
                "schema": "2.0",
                "header": {
                    "event_id": "event-help-001",
                    "event_type": "im.message.receive_v1",
                    "token": "test-token",
                },
                "event": {
                    "message": {
                        "message_type": "text",
                        "content": "{\"text\":\"查看帮助\"}",
                    },
                },
            },
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert len(sent_messages) == 1
    _assert_help_message(sent_messages[0])


@pytest.mark.parametrize(
    "keyword",
    [
        "帮助",
        "查看帮助",
        "你能做什么",
        "你能干什么",
        "你会干什么",
        "你有什么用",
        "你是谁",
        "怎么用",
        "怎么用你",
        "你会什么",
        "使用说明",
        "功能",
        "help",
    ],
)
def test_feishu_event_help_intent_keywords(monkeypatch, keyword):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("help intent must not generate report")
        ),
    )

    try:
        response = _post_feishu_text(
            client,
            f"event-help-keyword-{keyword}",
            keyword,
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert len(sent_messages) == 1
    _assert_help_message(sent_messages[0])


def test_feishu_event_unknown_intent_sends_fallback(monkeypatch):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("unknown intent must not generate report")
        ),
    )

    try:
        response = _post_feishu_text(
            client,
            "event-unknown-001",
            "随便乱问一句",
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert sent_messages == [UNKNOWN_MESSAGE_EXPECTED]


@pytest.mark.parametrize(
    "keyword",
    [
        "查看最新日报",
        "最新日报",
        "最近日报",
        "再发一下",
        "上一份日报",
        "刚才那份日报",
    ],
)
def test_feishu_event_latest_report_intent_keywords(monkeypatch, keyword):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("latest report intent must not generate report")
        ),
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.load_latest_report_cache",
        lambda: {
            "report": {
                "agent": "写日报虾",
                "title": "今日小龙虾运营日报",
                "markdown": "最新日报正文",
            }
        },
        raising=False,
    )

    try:
        response = _post_feishu_text(
            client,
            f"event-latest-keyword-{keyword}",
            keyword,
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert sent_messages == ["最新日报正文"]


@pytest.mark.parametrize(
    "keyword",
    [
        "生成今日日报",
        "生成日报",
        "经营日报",
        "今天生意怎么样",
        "今天经营情况",
        "汇总一下今天",
        "帮我看下今天",
    ],
)
def test_feishu_event_daily_report_intent_keywords(monkeypatch, keyword):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    called_sources = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: called_sources.append(source) or {"title": "ok"},
    )

    try:
        response = _post_feishu_text(
            client,
            f"event-daily-keyword-{keyword}",
            keyword,
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert called_sources == ["feishu_event"]


def test_feishu_event_intent_priority_help_over_latest_and_daily(monkeypatch):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("help priority must not generate report")
        ),
    )

    try:
        response = _post_feishu_text(
            client,
            "event-priority-help-001",
            "查看帮助，顺便查看最新日报和生成日报",
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert len(sent_messages) == 1
    _assert_help_message(sent_messages[0])


def test_feishu_event_intent_priority_latest_over_daily(monkeypatch):
    client = TestClient(app)
    old_token = settings.feishu_verification_token
    _set_feishu_verification_token("test-token")
    sent_messages = []
    monkeypatch.setattr(
        "app.services.feishu_adapter.send_feishu_text",
        lambda text: sent_messages.append(text) or True,
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("latest report priority must not generate report")
        ),
    )
    monkeypatch.setattr(
        "app.services.feishu_adapter.load_latest_report_cache",
        lambda: {
            "report": {
                "agent": "写日报虾",
                "title": "今日小龙虾运营日报",
                "markdown": "最新日报正文",
            }
        },
        raising=False,
    )

    try:
        response = _post_feishu_text(
            client,
            "event-priority-latest-001",
            "最新日报和经营日报都发一下",
        )
    finally:
        _set_feishu_verification_token(old_token)

    assert response.status_code == 200
    assert response.json() == {"ok": True, "handled": True}
    assert sent_messages == ["最新日报正文"]
