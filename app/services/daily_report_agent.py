import logging
from datetime import date
from typing import Any

from app.services.llm_service import generate_mock_suggestions, get_ai_mode


logger = logging.getLogger(__name__)


def _competitor_line(competitor: dict[str, Any]) -> str:
    return (
        f"- {competitor.get('name', '未知竞品')}："
        f"{competitor.get('promotion', '暂无促销')}，"
        f"热推 {competitor.get('hot_product', '未知产品')}"
    )


def generate_daily_report(
    order_analysis: dict[str, Any],
    reputation_analysis: dict[str, Any],
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    logger.info("DailyReportAgent started competitors=%s", len(competitors))

    order_summary = order_analysis["summary"]
    reputation_summary = reputation_analysis["summary"]
    suggestions = generate_mock_suggestions(
        "daily_report",
        {
            "order_summary": order_summary,
            "reputation_summary": reputation_summary,
        },
    )

    competitor_lines = (
        "\n".join(_competitor_line(item) for item in competitors)
        if competitors
        else "- 今日暂无竞品数据"
    )
    action_lines = "\n".join(f"- {item}" for item in suggestions)

    markdown = f"""# 今日小龙虾运营日报

日期：{date.today().isoformat()}

## 经营概览
- 订单 {order_summary['total_orders']} 单
- 销售额 {order_summary['total_revenue']} 元
- 客单价 {order_summary['average_order_value']} 元
- 爆款口味：{order_summary['top_product']}
- 高峰时段：{', '.join(order_summary['peak_periods']) or '暂无'}

## 舆情监控
- 舆情风险：{reputation_summary['risk_level']}
- 评论总数：{reputation_summary['total_comments']}
- 差评数量：{reputation_summary['negative_comments']}
- 风险关键词：{', '.join(reputation_summary['risk_keywords']) or '暂无'}

## 竞品观察
{competitor_lines}

## 明日行动建议
{action_lines}
"""

    logger.info(
        "DailyReportAgent finished orders=%s risk_level=%s",
        order_summary["total_orders"],
        reputation_summary["risk_level"],
    )

    return {
        "agent": "写日报虾",
        "title": "今日小龙虾运营日报",
        "markdown": markdown,
        "ai_mode": get_ai_mode(),
    }
