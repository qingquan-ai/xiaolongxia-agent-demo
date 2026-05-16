import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def reset_data_source_setting():
    original_data_source = getattr(settings, "data_source", "json")
    yield
    object.__setattr__(settings, "data_source", original_data_source)


def _set_data_source(value: str) -> None:
    object.__setattr__(settings, "data_source", value)


def test_load_orders_data_defaults_to_json(monkeypatch):
    from app.services import data_source

    if hasattr(settings, "data_source"):
        object.__setattr__(settings, "data_source", "")

    json_orders = [{"order_id": "json-order"}]
    monkeypatch.setattr(data_source, "load_orders", lambda: json_orders)
    monkeypatch.setattr(
        data_source,
        "read_bitable_records",
        lambda table_name: (_ for _ in ()).throw(
            AssertionError("default json mode must not read feishu bitable")
        ),
    )

    assert data_source.load_orders_data() == json_orders


def test_load_comments_data_uses_json_when_data_source_is_json(monkeypatch):
    from app.services import data_source

    _set_data_source("json")
    json_comments = [{"comment_id": "json-comment"}]
    monkeypatch.setattr(data_source, "load_comments", lambda: json_comments)
    monkeypatch.setattr(
        data_source,
        "read_bitable_records",
        lambda table_name: (_ for _ in ()).throw(
            AssertionError("json mode must not read feishu bitable")
        ),
    )

    assert data_source.load_comments_data() == json_comments


def test_load_competitors_data_falls_back_to_json_for_bad_data_source(monkeypatch):
    from app.services import data_source

    _set_data_source("bad_value")
    json_competitors = [{"name": "json-competitor"}]
    monkeypatch.setattr(data_source, "load_competitors", lambda: json_competitors)
    monkeypatch.setattr(
        data_source,
        "read_bitable_records",
        lambda table_name: (_ for _ in ()).throw(
            AssertionError("bad data source must fallback json")
        ),
    )

    assert data_source.load_competitors_data() == json_competitors


def test_load_orders_data_uses_feishu_bitable_records_and_transformer(monkeypatch):
    from app.services import data_source

    _set_data_source("feishu_bitable")
    monkeypatch.setattr(
        data_source,
        "read_bitable_records",
        lambda table_name: {
            "ok": True,
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
    monkeypatch.setattr(
        data_source,
        "load_orders",
        lambda: (_ for _ in ()).throw(
            AssertionError("successful feishu mode must not fallback json")
        ),
    )

    orders = data_source.load_orders_data()

    assert len(orders) == 2
    assert orders[0]["order_id"] == "order-1-1"
    assert orders[0]["amount"] == 100


def test_load_comments_data_uses_feishu_bitable_records_and_transformer(monkeypatch):
    from app.services import data_source

    _set_data_source("feishu_bitable")
    monkeypatch.setattr(
        data_source,
        "read_bitable_records",
        lambda table_name: {
            "ok": True,
            "records": [
                {
                    "record_id": "comment-1",
                    "fields": {
                        "日期": "2026-05-16",
                        "评分": 2,
                        "评论内容": "虾不够入味，上菜慢",
                    },
                }
            ],
        },
    )
    monkeypatch.setattr(
        data_source,
        "load_comments",
        lambda: (_ for _ in ()).throw(
            AssertionError("successful feishu mode must not fallback json")
        ),
    )

    comments = data_source.load_comments_data()

    assert comments == [
        {
            "comment_id": "comment-1",
            "platform": "未知平台",
            "store": "小龙虾人民广场店",
            "rating": 2,
            "content": "虾不够入味，上菜慢",
            "created_at": "2026-05-16 12:00:00",
            "replied": False,
        }
    ]


def test_load_competitors_data_uses_feishu_bitable_records_and_transformer(
    monkeypatch,
):
    from app.services import data_source

    _set_data_source("feishu_bitable")
    monkeypatch.setattr(
        data_source,
        "read_bitable_records",
        lambda table_name: {
            "ok": True,
            "records": [
                {
                    "record_id": "competitor-1",
                    "fields": {
                        "竞品门店": "隔壁虾王",
                        "促销动作": "满100减20",
                        "热卖品": "蒜蓉小龙虾",
                    },
                }
            ],
        },
    )
    monkeypatch.setattr(
        data_source,
        "load_competitors",
        lambda: (_ for _ in ()).throw(
            AssertionError("successful feishu mode must not fallback json")
        ),
    )

    competitors = data_source.load_competitors_data()

    assert competitors[0]["name"] == "隔壁虾王"
    assert competitors[0]["promotion"] == "满100减20"


@pytest.mark.parametrize(
    ("loader_name", "json_loader_name"),
    [
        ("load_orders_data", "load_orders"),
        ("load_comments_data", "load_comments"),
        ("load_competitors_data", "load_competitors"),
    ],
)
def test_feishu_bitable_read_failure_falls_back_to_json(
    monkeypatch,
    loader_name,
    json_loader_name,
):
    from app.services import data_source

    _set_data_source("feishu_bitable")
    fallback_data = [{"source": "json"}]
    monkeypatch.setattr(
        data_source,
        "read_bitable_records",
        lambda table_name: {"ok": False, "error": "bitable_records_fetch_failed"},
    )
    monkeypatch.setattr(data_source, json_loader_name, lambda: fallback_data)

    assert getattr(data_source, loader_name)() == fallback_data


@pytest.mark.parametrize(
    ("loader_name", "json_loader_name"),
    [
        ("load_orders_data", "load_orders"),
        ("load_comments_data", "load_comments"),
        ("load_competitors_data", "load_competitors"),
    ],
)
def test_feishu_bitable_empty_conversion_falls_back_to_json(
    monkeypatch,
    loader_name,
    json_loader_name,
):
    from app.services import data_source

    _set_data_source("feishu_bitable")
    fallback_data = [{"source": "json"}]
    monkeypatch.setattr(
        data_source,
        "read_bitable_records",
        lambda table_name: {"ok": True, "records": [{"record_id": "bad", "fields": {}}]},
    )
    monkeypatch.setattr(data_source, json_loader_name, lambda: fallback_data)

    assert getattr(data_source, loader_name)() == fallback_data


def test_generate_and_push_daily_report_uses_unified_data_source(monkeypatch):
    from app.services import feishu_adapter

    captured = {}
    monkeypatch.setattr(
        feishu_adapter,
        "load_orders_data",
        lambda: [
            {
                "order_id": "source-order",
                "product": "十三香小龙虾",
                "quantity": 1,
                "amount": 100,
                "order_time": "2026-05-16 18:30:00",
                "status": "completed",
            }
        ],
        raising=False,
    )
    monkeypatch.setattr(
        feishu_adapter,
        "load_comments_data",
        lambda: [
            {
                "comment_id": "source-comment",
                "rating": 5,
                "content": "很好吃",
                "replied": True,
            }
        ],
        raising=False,
    )
    monkeypatch.setattr(
        feishu_adapter,
        "load_competitors_data",
        lambda: [{"name": "隔壁虾王", "promotion": "满减", "hot_product": "蒜蓉"}],
        raising=False,
    )
    monkeypatch.setattr(
        feishu_adapter,
        "load_orders",
        lambda: (_ for _ in ()).throw(
            AssertionError("generate report must use load_orders_data")
        ),
    )
    monkeypatch.setattr(
        feishu_adapter,
        "load_comments",
        lambda: (_ for _ in ()).throw(
            AssertionError("generate report must use load_comments_data")
        ),
    )
    monkeypatch.setattr(
        feishu_adapter,
        "load_competitors",
        lambda: (_ for _ in ()).throw(
            AssertionError("generate report must use load_competitors_data")
        ),
    )
    monkeypatch.setattr(
        feishu_adapter,
        "save_latest_report_cache",
        lambda **kwargs: captured.setdefault("save", kwargs) or True,
    )
    monkeypatch.setattr(
        feishu_adapter,
        "append_report_history",
        lambda **kwargs: captured.setdefault("history", kwargs) or True,
    )
    monkeypatch.setattr(feishu_adapter, "send_feishu_text", lambda text: True)

    result = feishu_adapter.generate_and_push_daily_report(source="test")

    assert result["title"] == "今日小龙虾运营日报"
    assert captured["save"]["source"] == "test"
    assert captured["history"]["source"] == "test"
    assert captured["save"]["competitors"][0]["name"] == "隔壁虾王"
