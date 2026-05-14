from app.services.data_analysis_agent import analyze_orders
from app.services.daily_report_agent import generate_daily_report
from app.services.reputation_agent import analyze_reputation


def test_data_analysis_calculates_store_metrics():
    orders = [
        {
            "order_id": "O1",
            "store": "小龙虾人民广场店",
            "channel": "美团",
            "product": "十三香小龙虾",
            "quantity": 2,
            "amount": 176,
            "order_time": "2026-05-13 12:18:00",
            "status": "completed",
        },
        {
            "order_id": "O2",
            "store": "小龙虾人民广场店",
            "channel": "堂食",
            "product": "蒜蓉小龙虾",
            "quantity": 1,
            "amount": 98,
            "order_time": "2026-05-13 19:42:00",
            "status": "completed",
        },
    ]

    result = analyze_orders(orders)

    assert result["summary"]["total_orders"] == 2
    assert result["summary"]["total_revenue"] == 274
    assert result["summary"]["average_order_value"] == 137
    assert result["summary"]["top_product"] == "十三香小龙虾"
    assert "午市" in result["summary"]["peak_periods"]
    assert "晚市" in result["summary"]["peak_periods"]
    assert result["ai_mode"] == "mock"


def test_reputation_analysis_flags_negative_comment_risk():
    comments = [
        {
            "comment_id": "C1",
            "platform": "大众点评",
            "store": "小龙虾人民广场店",
            "rating": 2,
            "content": "虾不够入味，上菜也有点慢",
            "created_at": "2026-05-13 19:20:00",
            "replied": False,
        },
        {
            "comment_id": "C2",
            "platform": "美团",
            "store": "小龙虾人民广场店",
            "rating": 5,
            "content": "味道很好，服务也热情",
            "created_at": "2026-05-13 20:05:00",
            "replied": True,
        },
    ]

    result = analyze_reputation(comments)

    assert result["summary"]["total_comments"] == 2
    assert result["summary"]["negative_comments"] == 1
    assert result["summary"]["risk_level"] == "medium"
    assert result["priority_comments"][0]["comment_id"] == "C1"
    assert "慢" in result["summary"]["risk_keywords"]


def test_daily_report_combines_analysis_sections():
    order_analysis = {
        "summary": {
            "total_orders": 2,
            "total_revenue": 274,
            "average_order_value": 137,
            "top_product": "十三香小龙虾",
            "peak_periods": ["午市", "晚市"],
        },
        "suggestions": ["晚市加派打包人手"],
    }
    reputation_analysis = {
        "summary": {
            "total_comments": 2,
            "negative_comments": 1,
            "risk_level": "medium",
            "risk_keywords": ["慢", "不够入味"],
        },
        "suggestions": ["优先回复未处理差评"],
    }
    competitors = [
        {
            "name": "隔壁虾王",
            "promotion": "满100减20",
            "hot_product": "蒜蓉小龙虾",
        }
    ]

    report = generate_daily_report(order_analysis, reputation_analysis, competitors)

    assert report["title"] == "今日小龙虾运营日报"
    assert "订单 2 单" in report["markdown"]
    assert "舆情风险：medium" in report["markdown"]
    assert "隔壁虾王" in report["markdown"]
