import logging
import json
import re
from typing import Any

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


class _OpenRouterResponseError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def get_ai_mode() -> str:
    return "openrouter" if settings.is_openrouter_enabled else "mock"


def generate_mock_suggestions(task: str, context: dict[str, Any]) -> list[str]:
    if settings.is_openrouter_enabled:
        logger.info(
            "Generating AI suggestions task=%s provider=openrouter model=%s",
            task,
            settings.openrouter_model,
        )
        try:
            suggestions = _generate_openrouter_suggestions(task, context)
        except _OpenRouterResponseError as exc:
            logger.warning(
                "OpenRouter request returned non-2xx status task=%s status_code=%s fallback=mock",
                task,
                exc.status_code,
            )
        except httpx.TimeoutException:
            logger.warning(
                "OpenRouter request timed out task=%s timeout_seconds=%s fallback=mock",
                task,
                settings.llm_timeout_seconds,
            )
        except httpx.RequestError as exc:
            logger.warning(
                "OpenRouter request failed task=%s error_type=%s fallback=mock",
                task,
                exc.__class__.__name__,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning(
                "OpenRouter response parse failed task=%s error_type=%s fallback=mock",
                task,
                exc.__class__.__name__,
            )
        else:
            logger.info(
                "OpenRouter suggestions generated task=%s count=%s",
                task,
                len(suggestions),
            )
            return suggestions
    else:
        reason = "mode" if settings.llm_mode != "openrouter" else "missing_key"
        logger.info(
            "Generating AI suggestions task=%s provider=mock reason=%s",
            task,
            reason,
        )

    return _generate_mock_suggestions(task, context)


def _generate_mock_suggestions(task: str, context: dict[str, Any]) -> list[str]:
    logger.info(
        "Using mock AI suggestions task=%s mode=%s",
        task,
        get_ai_mode(),
    )

    if task == "data_analysis":
        top_product = context.get("top_product", "主推产品")
        return [
            f"继续把 {top_product} 放在首页推荐位，承接当前热销需求。",
            "晚市订单集中时提前备货，减少出餐和打包等待。",
            "对外卖渠道设置小份加购，提高客单价。",
        ]

    if task == "reputation":
        risk_level = context.get("risk_level", "low")
        return [
            f"当前舆情风险为 {risk_level}，优先处理未回复的低分评论。",
            "针对口味和出餐速度问题，用补偿券加解释话术降低二次扩散。",
            "把高频差评关键词同步给后厨和前厅班组。",
        ]

    if task == "daily_report":
        return [
            "明日重点关注晚市履约速度和差评回复闭环。",
            "将热销口味继续作为主推，同时观察竞品促销动作。",
        ]

    return ["mock 模式已生成基础建议，后续可替换为真实大模型调用。"]


def _generate_openrouter_suggestions(task: str, context: dict[str, Any]) -> list[str]:
    url = f"{settings.openrouter_base_url}/chat/completions"
    payload = {
        "model": settings.openrouter_model,
        "messages": _build_messages(task, context),
        "temperature": 0.3,
        "max_tokens": 500,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        response = client.post(url, headers=headers, json=payload)

    if not 200 <= response.status_code < 300:
        raise _OpenRouterResponseError(response.status_code)

    data = response.json()
    content = data["choices"][0]["message"]["content"]
    suggestions = _parse_suggestions(content)
    if not suggestions:
        raise ValueError("empty suggestions")
    return suggestions


def _build_messages(task: str, context: dict[str, Any]) -> list[dict[str, str]]:
    task_name = {
        "data_analysis": "订单经营分析",
        "reputation": "顾客评价和舆情处理",
        "daily_report": "每日经营日报动作建议",
    }.get(task, "小龙虾门店经营建议")
    context_json = json.dumps(context, ensure_ascii=False, default=str)

    return [
        {
            "role": "system",
            "content": (
                "你是小龙虾门店经营助手。请给出务实、简短、可执行的中文建议，"
                "不要解释技术实现，不要输出英文技术词。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"任务：{task_name}\n"
                f"门店数据：{context_json}\n"
                "请只返回 JSON 字符串数组，包含 2 到 3 条建议。"
                "示例：[\"建议一\", \"建议二\"]。不要返回 Markdown。"
            ),
        },
    ]


def _parse_suggestions(content: Any) -> list[str]:
    if isinstance(content, list):
        text = "\n".join(str(item) for item in content)
    else:
        text = str(content)

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        return _clean_suggestions(parsed)

    if isinstance(parsed, dict):
        for key in ("suggestions", "actions", "items"):
            value = parsed.get(key)
            if isinstance(value, list):
                return _clean_suggestions(value)

    lines = []
    for line in cleaned.splitlines():
        item = line.strip()
        if not item:
            continue
        item = re.sub(r"^[-*•]\s*", "", item)
        item = re.sub(r"^\d+[\.\)、]\s*", "", item)
        if item:
            lines.append(item)

    return _clean_suggestions(lines)


def _clean_suggestions(items: list[Any]) -> list[str]:
    suggestions = []
    for item in items:
        suggestion = str(item).strip().strip('"').strip("'")
        if suggestion:
            suggestions.append(suggestion)
    return suggestions[:3]
