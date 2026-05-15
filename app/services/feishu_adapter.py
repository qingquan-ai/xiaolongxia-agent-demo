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
from app.services.feishu_sender import send_feishu_text
from app.services.json_store import (
    append_report_history,
    load_comments,
    load_competitors,
    load_orders,
    save_latest_report_cache,
)
from app.services.reputation_agent import analyze_reputation


logger = logging.getLogger(__name__)

MAX_PROCESSED_EVENT_IDS = 500
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


def generate_and_push_daily_report(source: str) -> dict[str, Any]:
    order_analysis = analyze_orders(load_orders())
    reputation_analysis = analyze_reputation(load_comments())
    competitors = load_competitors()
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
        result = generate_and_push_daily_report(source="feishu_webhook")
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
        if "生成今日日报" not in text:
            logger.info(
                "Feishu event ignored reason=unsupported_text event_id=%s event_type=%s",
                event_id or "missing",
                event_type or "unknown",
            )
            return {"ok": True, "ignored": True}

        generate_and_push_daily_report(source="feishu_event")
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
