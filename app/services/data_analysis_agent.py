import logging
from collections import Counter
from datetime import datetime
from typing import Any

from app.services.llm_service import generate_mock_suggestions, get_ai_mode


logger = logging.getLogger(__name__)


def _period_name(order_time: str) -> str:
    try:
        hour = datetime.strptime(order_time, "%Y-%m-%d %H:%M:%S").hour
    except ValueError:
        return "其他"

    if 11 <= hour <= 14:
        return "午市"
    if 17 <= hour <= 21:
        return "晚市"
    if 22 <= hour or hour <= 2:
        return "夜宵"
    return "其他"


def analyze_orders(orders: list[dict[str, Any]]) -> dict[str, Any]:
    logger.info("DataAnalysisAgent started orders=%s", len(orders))

    completed_orders = [
        order for order in orders if order.get("status", "completed") == "completed"
    ]
    total_orders = len(completed_orders)
    total_revenue = sum(float(order.get("amount", 0)) for order in completed_orders)
    average_order_value = round(total_revenue / total_orders, 2) if total_orders else 0

    product_quantities: Counter[str] = Counter()
    channel_counts: Counter[str] = Counter()
    period_counts: Counter[str] = Counter()

    for order in completed_orders:
        product_quantities[str(order.get("product", "未知产品"))] += int(
            order.get("quantity", 1)
        )
        channel_counts[str(order.get("channel", "未知渠道"))] += 1
        period_counts[_period_name(str(order.get("order_time", "")))] += 1

    top_product = product_quantities.most_common(1)[0][0] if product_quantities else ""
    peak_periods = [period for period, _ in period_counts.most_common()]

    summary = {
        "total_orders": total_orders,
        "total_revenue": int(total_revenue)
        if total_revenue.is_integer()
        else round(total_revenue, 2),
        "average_order_value": int(average_order_value)
        if float(average_order_value).is_integer()
        else average_order_value,
        "top_product": top_product,
        "peak_periods": peak_periods,
        "channel_counts": dict(channel_counts),
        "product_quantities": dict(product_quantities),
    }

    suggestions = generate_mock_suggestions("data_analysis", summary)
    logger.info(
        "DataAnalysisAgent finished total_orders=%s total_revenue=%s top_product=%s",
        summary["total_orders"],
        summary["total_revenue"],
        summary["top_product"],
    )

    return {
        "agent": "数据分析虾",
        "summary": summary,
        "suggestions": suggestions,
        "ai_mode": get_ai_mode(),
    }
