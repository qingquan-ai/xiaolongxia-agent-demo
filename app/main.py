import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.logging import setup_logging
from app.models.schemas import FeishuWebhookPayload
from app.services.daily_report_agent import generate_daily_report
from app.services.data_analysis_agent import analyze_orders
from app.services.feishu_adapter import handle_feishu_webhook
from app.services.json_store import (
    load_comments,
    load_competitors,
    load_latest_report_cache,
    load_orders,
    save_latest_report_cache,
)
from app.services.reputation_agent import analyze_reputation


setup_logging()
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


def _now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def _dashboard_context_from_cache(cache: dict) -> dict:
    logger.info("Homepage dashboard source=cache")
    return {
        "app_name": settings.app_name,
        "llm_mode": settings.llm_mode,
        "order_analysis": cache["order_analysis"],
        "reputation_analysis": cache["reputation_analysis"],
        "competitors": cache["competitors"],
        "report": cache["report"],
    }


def _build_live_dashboard_context(reason: str) -> dict:
    logger.info("Homepage dashboard source=live reason=%s", reason)
    order_analysis = analyze_orders(load_orders())
    reputation_analysis = analyze_reputation(load_comments())
    competitors = load_competitors()
    report = generate_daily_report(
        order_analysis,
        reputation_analysis,
        competitors,
    )
    save_latest_report_cache(
        source="homepage_live",
        generated_at=_now_iso(),
        order_analysis=order_analysis,
        reputation_analysis=reputation_analysis,
        competitors=competitors,
        report=report,
    )
    return {
        "app_name": settings.app_name,
        "llm_mode": settings.llm_mode,
        "order_analysis": order_analysis,
        "reputation_analysis": reputation_analysis,
        "competitors": competitors,
        "report": report,
    }


def _build_dashboard_context() -> dict:
    cache = load_latest_report_cache()
    if cache is not None:
        return _dashboard_context_from_cache(cache)
    return _build_live_dashboard_context("cache_unavailable")


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
