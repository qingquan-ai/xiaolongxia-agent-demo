import logging
from typing import Any

from app.models.schemas import FeishuWebhookPayload
from app.services.daily_report_agent import generate_daily_report
from app.services.data_analysis_agent import analyze_orders
from app.services.json_store import load_comments, load_competitors, load_orders
from app.services.reputation_agent import analyze_reputation


logger = logging.getLogger(__name__)


def detect_intent(text: str) -> str:
    if "日报" in text or "总结" in text:
        return "daily_report"
    if "舆情" in text or "差评" in text or "评论" in text:
        return "reputation"
    if "订单" in text or "数据" in text or "分析" in text:
        return "data_analysis"
    return "help"


def handle_feishu_webhook(payload: FeishuWebhookPayload) -> dict[str, Any]:
    intent = detect_intent(payload.text)
    logger.info(
        "FeishuWebhook received event_id=%s sender=%s chat_id=%s intent=%s",
        payload.event_id,
        payload.sender,
        payload.chat_id,
        intent,
    )

    if intent == "data_analysis":
        result = analyze_orders(load_orders())
        reply = "数据分析虾已完成今日订单分析"
    elif intent == "reputation":
        result = analyze_reputation(load_comments())
        reply = "舆情监控虾已完成评论风险扫描"
    elif intent == "daily_report":
        order_analysis = analyze_orders(load_orders())
        reputation_analysis = analyze_reputation(load_comments())
        result = generate_daily_report(
            order_analysis,
            reputation_analysis,
            load_competitors(),
        )
        reply = "已生成今日运营日报，可复制到飞书群"
    else:
        result = {
            "supported_commands": [
                "生成今日小龙虾运营日报",
                "查看订单数据分析",
                "扫描差评舆情风险",
            ]
        }
        reply = "模拟飞书协作虾已收到消息，请发送日报、订单分析或舆情扫描指令"

    logger.info("FeishuWebhook handled event_id=%s intent=%s", payload.event_id, intent)
    return {
        "received": True,
        "intent": intent,
        "reply": reply,
        "result": result,
    }
