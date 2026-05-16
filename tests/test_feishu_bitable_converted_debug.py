import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def reset_debug_secret():
    original_debug_secret = settings.debug_api_secret
    yield
    object.__setattr__(settings, "debug_api_secret", original_debug_secret)


def _set_debug_secret() -> None:
    object.__setattr__(settings, "debug_api_secret", "debug-secret")


def _auth_headers() -> dict[str, str]:
    return {"X-Debug-Secret": "debug-secret"}


def _forbid_main_chain(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("converted debug endpoint must not generate report")
        ),
    )
    monkeypatch.setattr(
        "app.services.json_store.save_latest_report_cache",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("converted debug endpoint must not write latest_report")
        ),
    )
    monkeypatch.setattr(
        "app.services.json_store.append_report_history",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("converted debug endpoint must not write report_history")
        ),
    )


def test_feishu_bitable_converted_debug_rejects_missing_secret():
    _set_debug_secret()
    client = TestClient(app)

    response = client.get("/api/debug/feishu-bitable/orders/converted")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid debug secret"


def test_feishu_bitable_converted_debug_rejects_wrong_secret():
    _set_debug_secret()
    client = TestClient(app)

    response = client.get(
        "/api/debug/feishu-bitable/orders/converted",
        headers={"X-Debug-Secret": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid debug secret"


def test_feishu_bitable_converted_debug_rejects_unsupported_table():
    _set_debug_secret()
    client = TestClient(app)

    response = client.get(
        "/api/debug/feishu-bitable/unknown/converted",
        headers=_auth_headers(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported bitable table"


def test_feishu_bitable_converted_debug_returns_read_failure(monkeypatch):
    _set_debug_secret()
    _forbid_main_chain(monkeypatch)
    client = TestClient(app)
    failure = {
        "ok": False,
        "source": "feishu_bitable",
        "table": "orders",
        "error": "bitable_records_fetch_failed",
        "message": "Failed to fetch Feishu bitable records.",
    }
    monkeypatch.setattr("app.main.read_bitable_records", lambda table_name: failure)

    response = client.get(
        "/api/debug/feishu-bitable/orders/converted",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == failure


def test_feishu_bitable_converted_debug_returns_converted_orders(monkeypatch):
    _set_debug_secret()
    _forbid_main_chain(monkeypatch)
    client = TestClient(app)
    monkeypatch.setattr(
        "app.main.read_bitable_records",
        lambda table_name: {
            "ok": True,
            "source": "feishu_bitable",
            "table": table_name,
            "record_count": 1,
            "records": [
                {
                    "record_id": "order-1",
                    "fields": {
                        "日期": "2026-05-16",
                        "时段": "晚市",
                        "订单数": 2,
                        "销售额": 200,
                        "爆款产品": "十三香小龙虾",
                        "平台": "美团",
                    },
                }
            ],
        },
    )

    response = client.get(
        "/api/debug/feishu-bitable/orders/converted",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["source"] == "feishu_bitable"
    assert body["table"] == "orders"
    assert body["raw_record_count"] == 1
    assert body["converted_count"] == 2
    assert body["records"][0] == {
        "order_id": "order-1-1",
        "store": "小龙虾人民广场店",
        "channel": "美团",
        "product": "十三香小龙虾",
        "quantity": 1,
        "amount": 100,
        "order_time": "2026-05-16 18:30:00",
        "status": "completed",
    }


def test_feishu_bitable_converted_debug_returns_converted_comments(monkeypatch):
    _set_debug_secret()
    _forbid_main_chain(monkeypatch)
    client = TestClient(app)
    monkeypatch.setattr(
        "app.main.read_bitable_records",
        lambda table_name: {
            "ok": True,
            "source": "feishu_bitable",
            "table": table_name,
            "record_count": 1,
            "records": [
                {
                    "record_id": "comment-1",
                    "fields": {
                        "日期": "2026-05-16",
                        "平台": "大众点评",
                        "评分": 2,
                        "评论内容": "虾不够入味，上菜慢",
                        "处理状态": "未处理",
                    },
                }
            ],
        },
    )

    response = client.get(
        "/api/debug/feishu-bitable/comments/converted",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["table"] == "comments"
    assert body["raw_record_count"] == 1
    assert body["converted_count"] == 1
    assert body["records"][0] == {
        "comment_id": "comment-1",
        "platform": "大众点评",
        "store": "小龙虾人民广场店",
        "rating": 2,
        "content": "虾不够入味，上菜慢",
        "created_at": "2026-05-16 12:00:00",
        "replied": False,
    }


def test_feishu_bitable_converted_debug_returns_converted_competitors(monkeypatch):
    _set_debug_secret()
    _forbid_main_chain(monkeypatch)
    client = TestClient(app)
    monkeypatch.setattr(
        "app.main.read_bitable_records",
        lambda table_name: {
            "ok": True,
            "source": "feishu_bitable",
            "table": table_name,
            "record_count": 1,
            "records": [
                {
                    "record_id": "competitor-1",
                    "fields": {
                        "日期": "2026-05-16",
                        "竞品门店": "隔壁虾王",
                        "平台": "美团",
                        "促销动作": "满100减20",
                        "热卖品": "蒜蓉小龙虾",
                        "备注": "夜宵套餐",
                    },
                }
            ],
        },
    )

    response = client.get(
        "/api/debug/feishu-bitable/competitors/converted",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["table"] == "competitors"
    assert body["raw_record_count"] == 1
    assert body["converted_count"] == 1
    assert body["records"][0] == {
        "name": "隔壁虾王",
        "platform": "美团",
        "promotion": "满100减20",
        "hot_product": "蒜蓉小龙虾",
        "rating": 0,
        "note": "夜宵套餐",
        "date": "2026-05-16",
        "record_id": "competitor-1",
    }
