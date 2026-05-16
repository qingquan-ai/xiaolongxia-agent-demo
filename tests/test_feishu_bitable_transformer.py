from app.services.data_analysis_agent import analyze_orders
from app.services.feishu_bitable_transformer import (
    convert_bitable_records,
    convert_comment_records,
    convert_competitor_records,
    convert_order_records,
)
from app.services.reputation_agent import analyze_reputation


def test_convert_order_records_expands_aggregated_order():
    records = [
        {
            "record_id": "recxxxx",
            "fields": {
                "日期": "2026-05-16",
                "时段": "晚市",
                "订单数": 2,
                "销售额": 200,
                "爆款产品": "十三香小龙虾",
                "平台": "美团",
            },
        }
    ]

    orders = convert_order_records(records)

    assert len(orders) == 2
    assert orders[0]["order_id"] == "recxxxx-1"
    assert orders[1]["order_id"] == "recxxxx-2"
    for order in orders:
        assert order["store"] == "小龙虾人民广场店"
        assert order["channel"] == "美团"
        assert order["product"] == "十三香小龙虾"
        assert order["quantity"] == 1
        assert order["amount"] == 100
        assert order["order_time"] == "2026-05-16 18:30:00"
        assert order["status"] == "completed"


def test_convert_order_records_splits_total_revenue_evenly():
    records = [
        {
            "record_id": "rec-revenue",
            "fields": {
                "日期": "2026/05/16",
                "时段": "午市",
                "订单数": 4,
                "销售额": 400,
                "爆款产品": "蒜蓉小龙虾",
            },
        }
    ]

    orders = convert_order_records(records)

    assert len(orders) == 4
    assert {order["amount"] for order in orders} == {100}
    assert orders[0]["order_time"] == "2026-05-16 12:00:00"


def test_convert_order_records_uses_average_order_value_when_revenue_missing():
    records = [
        {
            "record_id": "rec-average",
            "fields": {
                "日期": "2026-05-16",
                "时段": "夜宵",
                "订单数": 3,
                "客单价": 56.5,
            },
        }
    ]

    orders = convert_order_records(records)

    assert len(orders) == 3
    assert {order["amount"] for order in orders} == {56.5}
    assert orders[0]["channel"] == "未知渠道"
    assert orders[0]["product"] == "未知产品"
    assert orders[0]["order_time"] == "2026-05-16 22:00:00"


def test_convert_order_records_filters_empty_or_invalid_records():
    records = [
        {"record_id": "empty", "fields": {}},
        {"record_id": "missing-count", "fields": {"日期": "2026-05-16", "销售额": 100}},
        {
            "record_id": "zero-count",
            "fields": {"日期": "2026-05-16", "订单数": 0, "销售额": 100},
        },
        {"record_id": "missing-date", "fields": {"订单数": 1, "销售额": 100}},
        {
            "record_id": "missing-money",
            "fields": {"日期": "2026-05-16", "订单数": 1},
        },
    ]

    assert convert_order_records(records) == []


def test_convert_order_records_supports_millisecond_timestamp_date():
    records = [
        {
            "record_id": "rec-ts",
            "fields": {
                "日期": 1778806080000,
                "时段": "其他",
                "订单数": 1,
                "销售额": 88,
            },
        }
    ]

    orders = convert_order_records(records)

    assert len(orders) == 1
    assert orders[0]["order_time"].endswith(" 12:00:00")
    assert len(orders[0]["order_time"]) == len("2026-05-15 12:00:00")


def test_convert_comment_records_maps_rating_content_and_reply_status():
    records = [
        {
            "record_id": "comment-1",
            "fields": {
                "日期": "2026-05-16",
                "平台": "大众点评",
                "评分": "2",
                "评论内容": "虾不够入味，上菜慢",
                "处理状态": "未处理",
                "备注": "需跟进",
            },
        }
    ]

    comments = convert_comment_records(records)

    assert comments == [
        {
            "comment_id": "comment-1",
            "platform": "大众点评",
            "store": "小龙虾人民广场店",
            "rating": 2,
            "content": "虾不够入味，上菜慢",
            "created_at": "2026-05-16 12:00:00",
            "replied": False,
            "note": "需跟进",
        }
    ]


def test_convert_comment_records_maps_replied_status():
    records = [
        {
            "record_id": "comment-replied",
            "fields": {
                "平台": "美团",
                "评分": 5,
                "评论内容": "很好吃",
                "处理状态": "已回复",
            },
        }
    ]

    comments = convert_comment_records(records)

    assert comments[0]["created_at"] == ""
    assert comments[0]["replied"] is True


def test_convert_comment_records_filters_empty_content():
    records = [
        {"record_id": "empty", "fields": {}},
        {"record_id": "blank-content", "fields": {"评论内容": "   ", "评分": 1}},
    ]

    assert convert_comment_records(records) == []


def test_convert_competitor_records_maps_fields():
    records = [
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
    ]

    competitors = convert_competitor_records(records)

    assert competitors == [
        {
            "name": "隔壁虾王",
            "platform": "美团",
            "promotion": "满100减20",
            "hot_product": "蒜蓉小龙虾",
            "rating": 0,
            "note": "夜宵套餐",
            "date": "2026-05-16",
            "record_id": "competitor-1",
        }
    ]


def test_convert_competitor_records_filters_missing_store_name():
    records = [
        {
            "record_id": "missing-name",
            "fields": {"促销动作": "满100减20", "热卖品": "蒜蓉小龙虾"},
        },
        {"record_id": "empty-action", "fields": {"竞品门店": "隔壁虾王"}},
    ]

    assert convert_competitor_records(records) == []


def test_convert_records_handles_complex_feishu_field_values():
    records = [
        {
            "record_id": "complex",
            "fields": {
                "日期": {"text": "2026-05-16"},
                "时段": {"name": "晚市"},
                "订单数": {"value": "1"},
                "销售额": {"value": "99"},
                "爆款产品": [{"text": "十三香小龙虾"}, {"name": "蒜蓉小龙虾"}],
                "平台": ["美团", {"name": "堂食"}],
            },
        }
    ]

    orders = convert_order_records(records)

    assert len(orders) == 1
    assert orders[0]["product"] == "十三香小龙虾、蒜蓉小龙虾"
    assert orders[0]["channel"] == "美团、堂食"


def test_converted_records_can_be_consumed_by_existing_agents():
    order_records = [
        {
            "record_id": "order-agent",
            "fields": {
                "日期": "2026-05-16",
                "时段": "午市",
                "订单数": 2,
                "销售额": 200,
                "爆款产品": "十三香小龙虾",
                "平台": "美团",
            },
        }
    ]
    comment_records = [
        {
            "record_id": "comment-agent",
            "fields": {
                "日期": "2026-05-16",
                "评分": 2,
                "评论内容": "出餐慢，虾不够入味",
                "处理状态": "未处理",
            },
        }
    ]

    order_analysis = analyze_orders(convert_order_records(order_records))
    reputation_analysis = analyze_reputation(convert_comment_records(comment_records))

    assert order_analysis["summary"]["total_orders"] == 2
    assert order_analysis["summary"]["total_revenue"] == 200
    assert reputation_analysis["summary"]["negative_comments"] == 1
    assert "慢" in reputation_analysis["summary"]["risk_keywords"]


def test_convert_bitable_records_dispatches_by_table_name():
    records = [
        {
            "record_id": "competitor-dispatch",
            "fields": {
                "竞品门店": "阿强龙虾馆",
                "促销动作": "双人套餐",
                "热卖品": "十三香小龙虾",
            },
        }
    ]

    competitors = convert_bitable_records("competitors", records)

    assert competitors[0]["name"] == "阿强龙虾馆"
    assert convert_bitable_records("unknown", records) == []
