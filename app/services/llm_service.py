import logging
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)


def get_ai_mode() -> str:
    return "mock" if settings.is_mock_mode else settings.llm_mode


def generate_mock_suggestions(task: str, context: dict[str, Any]) -> list[str]:
    logger.info(
        "Generating AI suggestions task=%s mode=%s model=%s",
        task,
        get_ai_mode(),
        settings.llm_model,
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
