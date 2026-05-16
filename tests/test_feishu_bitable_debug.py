import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def reset_bitable_settings():
    original_values = {
        "debug_api_secret": settings.debug_api_secret,
        "feishu_app_id": settings.feishu_app_id,
        "feishu_app_secret": settings.feishu_app_secret,
        "feishu_bitable_app_token": settings.feishu_bitable_app_token,
        "feishu_orders_table_id": settings.feishu_orders_table_id,
        "feishu_comments_table_id": settings.feishu_comments_table_id,
        "feishu_competitors_table_id": settings.feishu_competitors_table_id,
    }
    yield
    for key, value in original_values.items():
        object.__setattr__(settings, key, value)


def _set_bitable_config() -> None:
    object.__setattr__(settings, "debug_api_secret", "debug-secret")
    object.__setattr__(settings, "feishu_app_id", "app-id")
    object.__setattr__(settings, "feishu_app_secret", "app-secret")
    object.__setattr__(settings, "feishu_bitable_app_token", "bitable-token")
    object.__setattr__(settings, "feishu_orders_table_id", "orders-table")
    object.__setattr__(settings, "feishu_comments_table_id", "comments-table")
    object.__setattr__(settings, "feishu_competitors_table_id", "competitors-table")


def _auth_headers() -> dict[str, str]:
    return {"X-Debug-Secret": "debug-secret"}


def test_feishu_bitable_debug_rejects_missing_secret():
    _set_bitable_config()
    client = TestClient(app)

    response = client.get("/api/debug/feishu-bitable/orders")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid debug secret"


def test_feishu_bitable_debug_rejects_wrong_secret():
    _set_bitable_config()
    client = TestClient(app)

    response = client.get(
        "/api/debug/feishu-bitable/orders",
        headers={"X-Debug-Secret": "wrong-secret"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid debug secret"


def test_feishu_bitable_debug_allows_missing_secret_config(monkeypatch):
    _set_bitable_config()
    object.__setattr__(settings, "debug_api_secret", "")
    client = TestClient(app)

    monkeypatch.setattr(
        "app.services.feishu_bitable_service.httpx.post",
        lambda *args, **kwargs: FakeResponse(
            200,
            {"code": 0, "tenant_access_token": "tenant-token"},
        ),
    )
    monkeypatch.setattr(
        "app.services.feishu_bitable_service.httpx.get",
        lambda *args, **kwargs: FakeResponse(
            200,
            {"code": 0, "data": {"items": []}},
        ),
    )

    response = client.get("/api/debug/feishu-bitable/orders")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "source": "feishu_bitable",
        "table": "orders",
        "record_count": 0,
        "records": [],
    }


def test_feishu_bitable_debug_rejects_unsupported_table():
    _set_bitable_config()
    client = TestClient(app)

    response = client.get(
        "/api/debug/feishu-bitable/unknown",
        headers=_auth_headers(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported bitable table"


def test_feishu_bitable_debug_returns_missing_config():
    object.__setattr__(settings, "debug_api_secret", "debug-secret")
    object.__setattr__(settings, "feishu_app_id", "")
    object.__setattr__(settings, "feishu_app_secret", "")
    object.__setattr__(settings, "feishu_bitable_app_token", "")
    object.__setattr__(settings, "feishu_orders_table_id", "")
    client = TestClient(app)

    response = client.get(
        "/api/debug/feishu-bitable/orders",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["source"] == "feishu_bitable"
    assert body["table"] == "orders"
    assert body["error"] == "missing_config"


def test_feishu_bitable_debug_returns_token_failure(monkeypatch):
    _set_bitable_config()
    client = TestClient(app)

    monkeypatch.setattr(
        "app.services.feishu_bitable_service.httpx.post",
        lambda *args, **kwargs: FakeResponse(
            200,
            {"code": 99991663, "msg": "invalid app credential"},
        ),
    )

    response = client.get(
        "/api/debug/feishu-bitable/orders",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "tenant_access_token_failed"


def test_feishu_bitable_debug_returns_records_failure(monkeypatch):
    _set_bitable_config()
    client = TestClient(app)

    monkeypatch.setattr(
        "app.services.feishu_bitable_service.httpx.post",
        lambda *args, **kwargs: FakeResponse(
            200,
            {"code": 0, "tenant_access_token": "tenant-token"},
        ),
    )
    monkeypatch.setattr(
        "app.services.feishu_bitable_service.httpx.get",
        lambda *args, **kwargs: FakeResponse(
            403,
            {"code": 99991663, "msg": "forbidden"},
        ),
    )

    response = client.get(
        "/api/debug/feishu-bitable/orders",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"] == "bitable_records_fetch_failed"


def test_feishu_bitable_debug_returns_records(monkeypatch):
    _set_bitable_config()
    client = TestClient(app)
    called_urls = []

    def fake_post(*args, **kwargs):
        return FakeResponse(200, {"code": 0, "tenant_access_token": "tenant-token"})

    def fake_get(url, *args, **kwargs):
        called_urls.append(url)
        return FakeResponse(
            200,
            {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "record_id": "recxxxx",
                            "fields": {"日期": "2026-05-16", "订单数": 5},
                        }
                    ]
                },
            },
        )

    monkeypatch.setattr("app.services.feishu_bitable_service.httpx.post", fake_post)
    monkeypatch.setattr("app.services.feishu_bitable_service.httpx.get", fake_get)
    monkeypatch.setattr(
        "app.main.generate_and_push_daily_report",
        lambda source: (_ for _ in ()).throw(
            AssertionError("debug bitable endpoint must not generate report")
        ),
    )

    response = client.get(
        "/api/debug/feishu-bitable/orders",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "source": "feishu_bitable",
        "table": "orders",
        "record_count": 1,
        "records": [
            {
                "record_id": "recxxxx",
                "fields": {"日期": "2026-05-16", "订单数": 5},
            }
        ],
    }
    assert called_urls == [
        "https://open.feishu.cn/open-apis/bitable/v1/apps/bitable-token/tables/orders-table/records"
    ]
