import json
import logging
from collections import deque
from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.schemas import FeishuWebhookPayload
from app.services.daily_report_agent import generate_daily_report
from app.services.data_analysis_agent import analyze_orders
from app.services.data_source import (
    load_comments_data,
    load_competitors_data,
    load_orders_data,
)
from app.services.feishu_sender import send_feishu_text
from app.services.json_store import (
    append_report_history,
    load_comments,
    load_competitors,
    load_latest_report_cache,
    load_orders,
    save_latest_report_cache,
)
from app.services.reputation_agent import analyze_reputation


logger = logging.getLogger(__name__)

MAX_PROCESSED_EVENT_IDS = 500
LATEST_REPORT_EMPTY_MESSAGE = "暂无日报，请先发送‘生成今日日报’。"
HELP_COMMANDS_MESSAGE = (
    "我是小龙虾 AI 日报助手，帮你自动汇总订单、评论和竞品信息，生成每日经营日报和明日行动建议。\n\n"
    "我可以帮你：\n"
    "- 看今日订单、销售额、客单价和爆款产品\n"
    "- 提醒差评、口味反馈、出餐慢等舆情风险\n"
    "- 整理竞品促销和热卖品\n"
    "- 给出明日备货、排班、差评回复和主推建议\n"
    "- 每天 22:00 自动推送日报\n\n"
    "你可以这样问：\n"
    "- 今天生意怎么样\n"
    "- 帮我看下今天经营情况\n"
    "- 生成今日日报\n"
    "- 查看最新日报\n"
    "- 刚才那份日报再发一下"
)
HELP_INTENT_KEYWORDS = (
    "帮助",
    "查看帮助",
    "你能干什么",
    "你有什么用",
    "怎么用你",
    "你会什么",
    "使用说明",
    "help",
)
LATEST_REPORT_INTENT_KEYWORDS = (
    "查看最新日报",
    "最新日报",
    "最近日报",
    "再发一下",
    "上一份日报",
    "刚才那份日报",
)
DAILY_REPORT_INTENT_KEYWORDS = (
    "生成今日日报",
    "生成日报",
    "经营日报",
    "今天生意怎么样",
    "今天经营情况",
    "汇总一下今天",
    "帮我看下今天",
)
_processed_event_ids: set[str] = set()
_processed_event_id_queue: deque[str] = deque()


class FeishuEventForbiddenError(Exception):
    pass


def _now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def _validate_event_token(token: str | None) -> None:
    expected_token = settings.feishu_verification_token
    if not expected_token:
        logger.warning("Feishu event token check skipped reason=missing_config")
        return
    if token != expected_token:
        logger.warning("Feishu event token check failed")
        raise FeishuEventForbiddenError()


def _remember_event_id(event_id: str) -> bool:
    if event_id in _processed_event_ids:
        return False

    _processed_event_ids.add(event_id)
    _processed_event_id_queue.append(event_id)
    while len(_processed_event_id_queue) > MAX_PROCESSED_EVENT_IDS:
        expired_event_id = _processed_event_id_queue.popleft()
        _processed_event_ids.discard(expired_event_id)
    return True


def _extract_event_id(body: dict[str, Any], headers: Mapping[str, str]) -> str:
    header = body.get("header") if isinstance(body.get("header"), dict) else {}
    event_id = header.get("event_id") or body.get("event_id")
    if event_id:
        return str(event_id)

    for header_name in ("x-lark-request-id", "x-request-id"):
        header_value = headers.get(header_name)
        if header_value:
            return str(header_value)
    return ""


def _extract_event_type(body: dict[str, Any]) -> str:
    header = body.get("header") if isinstance(body.get("header"), dict) else {}
    event_type = header.get("event_type") or body.get("event_type")
    return str(event_type or "")


def _extract_event_token(body: dict[str, Any]) -> str | None:
    token = body.get("token")
    if token:
        return str(token)

    header = body.get("header") if isinstance(body.get("header"), dict) else {}
    header_token = header.get("token")
    return str(header_token) if header_token else None


def _extract_message_text(body: dict[str, Any]) -> str:
    event = body.get("event")
    if not isinstance(event, dict):
        return ""

    message = event.get("message")
    if not isinstance(message, dict):
        return ""

    content = message.get("content")
    if isinstance(content, str):
        try:
            content_data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Feishu event message ignored reason=invalid_content_json")
            return ""
    elif isinstance(content, dict):
        content_data = content
    else:
        return ""

    text = content_data.get("text")
    return str(text) if text else ""


def _latest_report_message() -> str:
    latest_report = load_latest_report_cache()
    if latest_report is None:
        return LATEST_REPORT_EMPTY_MESSAGE

    report = latest_report.get("report")
    if not isinstance(report, dict):
        logger.warning("Feishu latest report skipped reason=report_not_dict")
        return LATEST_REPORT_EMPTY_MESSAGE

    markdown = report.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        logger.warning("Feishu latest report skipped reason=missing_markdown")
        return LATEST_REPORT_EMPTY_MESSAGE

    return markdown


def _send_latest_report() -> None:
    send_feishu_text(_latest_report_message())


def _send_help_commands() -> None:
    send_feishu_text(HELP_COMMANDS_MESSAGE)


def generate_and_push_daily_report(source: str) -> dict[str, Any]:
    orders = load_orders_data()
    comments = load_comments_data()
    competitors = load_competitors_data()

    order_analysis = analyze_orders(orders)
    reputation_analysis = analyze_reputation(comments)
    result = generate_daily_report(
        order_analysis,
        reputation_analysis,
        competitors,
    )
    generated_at = _now_iso()
    save_latest_report_cache(
        source=source,
        generated_at=generated_at,
        order_analysis=order_analysis,
        reputation_analysis=reputation_analysis,
        competitors=competitors,
        report=result,
    )
    append_report_history(
        source=source,
        generated_at=generated_at,
        order_analysis=order_analysis,
        reputation_analysis=reputation_analysis,
        competitors=competitors,
        report=result,
    )
    try:
        markdown = result.get("markdown") if isinstance(result, dict) else None
        if isinstance(markdown, str) and markdown.strip():
            send_feishu_text(markdown)
        else:
            logger.warning("Feishu push skipped reason=missing_report_markdown")
    except Exception as exc:
        logger.warning(
            "Feishu push skipped reason=unexpected_error error_type=%s",
            exc.__class__.__name__,
        )
    return result


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    normalized_text = text.lower()
    return any(keyword.lower() in normalized_text for keyword in keywords)


def detect_intent(text: str) -> str:
    if _contains_any_keyword(text, HELP_INTENT_KEYWORDS):
        return "help"
    if _contains_any_keyword(text, LATEST_REPORT_INTENT_KEYWORDS):
        return "latest_report"
    if _contains_any_keyword(text, DAILY_REPORT_INTENT_KEYWORDS):
        return "daily_report"
    if "日报" in text or "总结" in text:
        return "daily_report"
    if "舆情" in text or "差评" in text or "评论" in text:
        return "reputation"
    if "订单" in text or "数据" in text or "分析" in text:
        return "data_analysis"
    return "unknown"


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
        result = generate_and_push_daily_report(source="feishu_webhook")
        reply = "已生成今日运营日报，可复制到飞书群"
    elif intent == "latest_report":
        _send_latest_report()
        result = {"sent": True}
        reply = "已发送最新日报"
    else:
        _send_help_commands()
        result = {
            "supported_commands": [
                "生成今日日报",
                "查看最新日报",
                "查看帮助",
            ]
        }
        reply = "已发送帮助说明"

    logger.info("FeishuWebhook handled event_id=%s intent=%s", payload.event_id, intent)
    return {
        "received": True,
        "intent": intent,
        "reply": reply,
        "result": result,
    }


def handle_feishu_event_subscription(
    body: dict[str, Any],
    headers: Mapping[str, str],
) -> dict[str, Any]:
    if "challenge" in body:
        _validate_event_token(_extract_event_token(body))
        logger.info("Feishu event challenge handled")
        return {"challenge": body["challenge"]}

    _validate_event_token(_extract_event_token(body))

    event_id = _extract_event_id(body, headers)
    event_type = _extract_event_type(body)
    if event_id:
        if not _remember_event_id(event_id):
            logger.info(
                "Feishu event skipped reason=duplicate event_id=%s event_type=%s",
                event_id,
                event_type,
            )
            return {"ok": True, "duplicate": True}
    else:
        logger.info("Feishu event handling without event_id event_type=%s", event_type)

    logger.info(
        "Feishu event sync handling started event_id=%s event_type=%s",
        event_id or "missing",
        event_type or "unknown",
    )

    try:
        text = _extract_message_text(body)
        intent = detect_intent(text)
        if intent == "help":
            _send_help_commands()
        elif intent == "latest_report":
            _send_latest_report()
        elif intent == "daily_report":
            generate_and_push_daily_report(source="feishu_event")
        else:
            logger.info(
                "Feishu event ignored reason=unsupported_text event_id=%s event_type=%s intent=%s",
                event_id or "missing",
                event_type or "unknown",
                intent,
            )
            return {"ok": True, "ignored": True}
    except Exception as exc:
        logger.warning(
            "Feishu event sync handling failed event_id=%s error_type=%s",
            event_id or "missing",
            exc.__class__.__name__,
        )
        return {"ok": True, "handled": False}

    logger.info(
        "Feishu event sync handling finished event_id=%s event_type=%s",
        event_id or "missing",
        event_type or "unknown",
    )
    return {"ok": True, "handled": True}
