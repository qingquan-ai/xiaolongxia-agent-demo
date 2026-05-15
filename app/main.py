import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.logging import setup_logging
from app.models.schemas import FeishuWebhookPayload
from app.services.daily_report_agent import generate_daily_report
from app.services.data_analysis_agent import analyze_orders
from app.services.feishu_adapter import (
    FeishuEventForbiddenError,
    handle_feishu_event_subscription,
    handle_feishu_webhook,
)
from app.services.json_store import (
    load_comments,
    load_competitors,
    load_latest_report_cache,
    load_orders,
)
from app.services.reputation_agent import analyze_reputation


setup_logging()
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


EMPTY_REPORT_MESSAGE = "暂无日报，请在飞书群 @机器人 发送‘生成今日日报’。"


def _summary_dict(analysis: Any) -> dict[str, Any]:
    if not isinstance(analysis, dict):
        return {}
    summary = analysis.get("summary")
    return summary if isinstance(summary, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _format_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_generated_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "时间未记录"

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M")


def _clean_markdown_line(line: str) -> str:
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", line)
    cleaned = re.sub(r"^\s*[-*]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*\d+[.、]\s*", "", cleaned)
    return cleaned.strip()


def _extract_markdown_section(markdown: str, section_title: str) -> list[str]:
    lines: list[str] = []
    in_section = False
    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if in_section:
                break
            if heading == section_title:
                in_section = True
            continue
        if in_section:
            cleaned = _clean_markdown_line(raw_line)
            if cleaned:
                lines.append(cleaned)
    return lines


def format_peak_hour_items(peak_periods: Any) -> list[str]:
    peak_hour_map = {
        "午市": "午市 11:30-13:30",
        "晚市": "晚市 17:30-20:00",
        "夜宵": "夜宵 21:00-23:30",
    }
    formatted = []
    for period in _as_list(peak_periods):
        period_text = str(period)
        formatted.append(peak_hour_map.get(period_text, period_text))
    return formatted or ["暂未形成明显高峰"]


def format_peak_hours(peak_periods: Any) -> str:
    return "｜".join(format_peak_hour_items(peak_periods))


def build_business_overview(order_analysis: Any) -> dict[str, str]:
    summary = _summary_dict(order_analysis)
    peak_hours = format_peak_hours(summary.get("peak_periods"))
    top_product = summary.get("top_product") or "暂未统计"
    total_orders = summary.get("total_orders", 0)
    total_revenue = summary.get("total_revenue", 0)
    average_order_value = summary.get("average_order_value", 0)
    total_orders_text = _format_number(total_orders)
    total_revenue_text = _format_number(total_revenue)
    average_order_value_text = _format_number(average_order_value)
    return {
        "orders": total_orders_text,
        "revenue": total_revenue_text,
        "average_order_value": average_order_value_text,
        "headline": f"{total_orders_text} 单",
        "metrics": f"销售额 {total_revenue_text} 元｜客单价 {average_order_value_text} 元",
        "body": f"今日完成 {total_orders_text} 单，销售额 {total_revenue_text} 元，客单价 {average_order_value_text} 元。",
        "conclusion": f"爆款产品是{top_product}，继续作为主推。",
        "peak_hours": peak_hours,
        "top_product": str(top_product),
    }


def build_reputation_risk(reputation_analysis: Any) -> dict[str, str]:
    summary = _summary_dict(reputation_analysis)
    risk_level = summary.get("risk_level")
    risk_label_map = {
        "high": "高风险",
        "medium": "1 条差评待处理",
        "low": "较平稳",
    }
    risk_label = risk_label_map.get(str(risk_level), "需关注")
    keywords = "、".join(str(item) for item in _as_list(summary.get("risk_keywords")))
    keywords = keywords or "暂无明显风险词"
    total_comments = summary.get("total_comments", 0)
    negative_comments = summary.get("negative_comments", 0)
    total_comments_text = _format_number(total_comments)
    negative_comments_text = _format_number(negative_comments)
    return {
        "headline": risk_label,
        "pending": f"{negative_comments_text} 条差评",
        "body": (
            f"今天收到 {total_comments_text} 条评论，其中 {negative_comments_text} 条低分评价。"
            f"风险关键词：{keywords}。建议今天先完成差评回复，并同步后厨复查。"
        ),
        "keywords": keywords,
        "next_step": "建议今天先完成差评回复，并同步后厨复查。",
    }


def build_competitor_summary(competitors: Any) -> list[dict[str, str]]:
    if not isinstance(competitors, list) or not competitors:
        return [
            {
                "name": "暂无竞品信息",
                "platform": "-",
                "promotion": "先按现有热销口味和门店节奏推进",
                "hot_product": "-",
            }
        ]

    rows: list[dict[str, str]] = []
    for item in competitors[:2]:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or "周边门店"
        platform = item.get("platform") or "线上平台"
        promotion = item.get("promotion") or "常规活动"
        hot_product = item.get("hot_product") or "主推产品"
        rows.append(
            {
                "name": str(name),
                "platform": str(platform),
                "promotion": str(promotion),
                "hot_product": str(hot_product),
            }
        )
    return rows or [
        {
            "name": "暂无竞品信息",
            "platform": "-",
            "promotion": "今天暂无可用的竞品信息",
            "hot_product": "-",
        }
    ]


def build_tomorrow_actions(markdown: str, order_analysis: Any) -> list[str]:
    top_product = _summary_dict(order_analysis).get("top_product") or "主卖口味"
    return [
        "晚市前 30 分钟完成备货和排班确认",
        "优先回复差评并记录问题原因",
        f"继续主推{top_product}",
        "观察竞品套餐和夜宵时段促销",
    ]


def build_tomorrow_focus(tomorrow_actions: list[str]) -> list[str]:
    focus_items: list[str] = []
    for action in tomorrow_actions:
        if ("晚市" in action or "后厨" in action or "备好" in action) and "晚市履约" not in focus_items:
            focus_items.append("晚市履约")
        elif ("差评" in action or "低分" in action or "前厅" in action) and "差评回复" not in focus_items:
            focus_items.append("差评回复")
        elif ("套餐" in action or "运营" in action or "促销" in action) and "套餐观察" not in focus_items:
            focus_items.append("套餐观察")
    return focus_items[:2] or ["晚市履约", "差评回复"]


def build_kpi_cards(
    business_overview: dict[str, str],
    reputation_risk: dict[str, str],
    tomorrow_focus: list[str],
) -> list[dict[str, str]]:
    focus_text = "｜".join(tomorrow_focus)
    return [
        {
            "label": "今日订单",
            "value": business_overview["headline"],
            "meta": business_overview["metrics"],
            "note": "看订单、销售额和客单价是否稳定。",
        },
        {
            "label": "爆款产品",
            "value": business_overview["top_product"],
            "meta": "继续作为主推",
            "note": "高峰前优先备货，避免临时补货影响出餐。",
        },
        {
            "label": "舆情待处理",
            "value": reputation_risk["pending"],
            "meta": f"关键词：{reputation_risk['keywords']}",
            "note": reputation_risk["next_step"],
        },
        {
            "label": "明日重点",
            "value": f"{len(tomorrow_focus)} 项行动",
            "meta": focus_text,
            "note": "先盯最影响明天经营的两件事。",
        },
    ]


def build_operation_review(
    business_overview: dict[str, str],
    reputation_risk: dict[str, str],
    peak_hours: list[str],
    tomorrow_actions: list[str],
) -> dict[str, str]:
    return {
        "performance": f"{business_overview['body']}{business_overview['conclusion']}",
        "peak_hours": "；".join(peak_hours),
        "risk_problem": (
            f"{reputation_risk['body']}今晚重点盯住出餐速度、口味稳定和分量反馈。"
        ),
        "tomorrow_focus": " ".join(tomorrow_actions[:2]) or "明天先稳住备货和差评回复。",
    }


def _build_customer_dashboard(cache: dict[str, Any]) -> dict[str, Any]:
    order_analysis = cache.get("order_analysis")
    reputation_analysis = cache.get("reputation_analysis")
    competitors = cache.get("competitors")
    report = cache.get("report") if isinstance(cache.get("report"), dict) else {}
    markdown = report.get("markdown") if isinstance(report, dict) else ""
    markdown = markdown if isinstance(markdown, str) else ""
    business_overview = build_business_overview(order_analysis)
    reputation_risk = build_reputation_risk(reputation_analysis)
    competitor_summary = build_competitor_summary(competitors)
    tomorrow_actions = build_tomorrow_actions(markdown, order_analysis)
    tomorrow_focus = build_tomorrow_focus(tomorrow_actions)
    peak_hours = format_peak_hour_items(_summary_dict(order_analysis).get("peak_periods"))
    return {
        "generated_at_text": _format_generated_at(cache.get("generated_at")),
        "kpi_cards": build_kpi_cards(
            business_overview,
            reputation_risk,
            tomorrow_focus,
        ),
        "business_overview": business_overview,
        "reputation_risk": reputation_risk,
        "competitor_summary": competitor_summary,
        "peak_hours": peak_hours,
        "tomorrow_actions": tomorrow_actions,
        "tomorrow_focus": "｜".join(tomorrow_focus),
        "operation_review": build_operation_review(
            business_overview,
            reputation_risk,
            peak_hours,
            tomorrow_actions,
        ),
    }


def _dashboard_context_from_cache(cache: dict[str, Any]) -> dict[str, Any]:
    logger.info("Homepage dashboard source=cache")
    return {
        "app_name": settings.app_name,
        "has_report": True,
        "customer_dashboard": _build_customer_dashboard(cache),
    }


def _empty_dashboard_context() -> dict[str, Any]:
    logger.info("Homepage dashboard source=empty reason=cache_unavailable")
    return {
        "app_name": settings.app_name,
        "has_report": False,
        "empty_message": EMPTY_REPORT_MESSAGE,
    }


def _build_dashboard_context() -> dict:
    cache = load_latest_report_cache()
    if cache is not None:
        return _dashboard_context_from_cache(cache)
    return _empty_dashboard_context()


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    logger.info("Homepage requested")
    context = _build_dashboard_context()
    context["request"] = request
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=context,
    )


@app.get("/health")
def health():
    logger.info("Health check requested")
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "llm_mode": settings.llm_mode,
    }


@app.get("/api/agents/data-analysis")
def get_data_analysis():
    logger.info("API requested data analysis")
    return analyze_orders(load_orders())


@app.post("/api/agents/data-analysis/run")
def run_data_analysis():
    logger.info("API triggered data analysis")
    return analyze_orders(load_orders())


@app.get("/api/agents/reputation")
def get_reputation_analysis():
    logger.info("API requested reputation analysis")
    return analyze_reputation(load_comments())


@app.post("/api/agents/reputation/run")
def run_reputation_analysis():
    logger.info("API triggered reputation analysis")
    return analyze_reputation(load_comments())


@app.get("/api/reports/today")
def get_today_report():
    logger.info("API requested daily report")
    order_analysis = analyze_orders(load_orders())
    reputation_analysis = analyze_reputation(load_comments())
    return generate_daily_report(order_analysis, reputation_analysis, load_competitors())


@app.post("/api/reports/daily/generate")
def generate_report():
    logger.info("API triggered daily report")
    order_analysis = analyze_orders(load_orders())
    reputation_analysis = analyze_reputation(load_comments())
    return generate_daily_report(order_analysis, reputation_analysis, load_competitors())


@app.post("/api/webhook/feishu")
def feishu_webhook(payload: FeishuWebhookPayload):
    return handle_feishu_webhook(payload)


@app.post("/api/feishu/events")
async def feishu_events(request: Request):
    try:
        body = await request.json()
    except ValueError:
        logger.warning("Feishu event ignored reason=invalid_json")
        return {"ok": True, "ignored": True}

    if not isinstance(body, dict):
        logger.warning("Feishu event ignored reason=invalid_body")
        return {"ok": True, "ignored": True}

    try:
        return handle_feishu_event_subscription(body, request.headers)
    except FeishuEventForbiddenError as exc:
        raise HTTPException(status_code=403, detail="forbidden") from exc
