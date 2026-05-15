import logging
import json
from typing import Any

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


class _OpenRouterResponseError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class LLMOutputParseError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


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
                "OpenRouter request returned non-2xx status task=%s status_code=%s fallback=mock reason=http_status",
                task,
                exc.status_code,
            )
        except httpx.TimeoutException:
            logger.warning(
                "OpenRouter request timed out task=%s timeout_seconds=%s fallback=mock reason=timeout",
                task,
                settings.llm_timeout_seconds,
            )
        except httpx.RequestError as exc:
            logger.warning(
                "OpenRouter request failed task=%s error_type=%s fallback=mock reason=request_error",
                task,
                exc.__class__.__name__,
            )
        except LLMOutputParseError as exc:
            logger.warning(
                "OpenRouter output parse failed task=%s fallback=mock reason=%s",
                task,
                exc.reason,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            logger.warning(
                "OpenRouter response structure invalid task=%s error_type=%s fallback=mock reason=invalid_response",
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
        "max_tokens": 300,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://124.222.231.10:8000",
        "X-Title": "xiaolongxia-agent-demo",
    }

    with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
        response = client.post(url, headers=headers, json=payload)

    if not 200 <= response.status_code < 300:
        raise _OpenRouterResponseError(response.status_code)

    try:
        data = response.json()
    except ValueError:
        raise LLMOutputParseError("invalid_response_json") from None

    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise LLMOutputParseError("empty_content")
    if not content.strip():
        raise LLMOutputParseError("empty_content")

    suggestions = _parse_suggestions(content)
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
                "请只返回 JSON 字符串数组，最多 3 条建议，每条不超过 50 个中文字符。"
                "示例：[\"建议一\", \"建议二\"]。不要返回 Markdown。"
            ),
        },
    ]


def _parse_suggestions(content: Any) -> list[str]:
    if not isinstance(content, str):
        raise LLMOutputParseError("empty_content")

    cleaned = content.strip()
    if not cleaned:
        raise LLMOutputParseError("empty_content")

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        raise LLMOutputParseError("invalid_json") from None

    if not isinstance(parsed, list):
        raise LLMOutputParseError("not_list")
    if not parsed:
        raise LLMOutputParseError("empty_list")

    suggestions = _clean_suggestions(parsed)
    if not suggestions:
        raise LLMOutputParseError("no_string_items")
    return suggestions


def _clean_suggestions(items: list[Any]) -> list[str]:
    suggestions = []
    for item in items:
        if not isinstance(item, str):
            continue
        suggestion = item.strip()
        if suggestion:
            suggestions.append(suggestion)
    return suggestions[:3]
