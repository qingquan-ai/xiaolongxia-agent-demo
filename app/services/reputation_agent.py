import logging
from typing import Any

from app.services.llm_service import generate_mock_suggestions, get_ai_mode


logger = logging.getLogger(__name__)

RISK_KEYWORDS = ["慢", "不够入味", "不新鲜", "冷", "少", "贵", "差", "异味"]


def _comment_risk_keywords(content: str) -> list[str]:
    return [keyword for keyword in RISK_KEYWORDS if keyword in content]


def analyze_reputation(comments: list[dict[str, Any]]) -> dict[str, Any]:
    logger.info("ReputationAgent started comments=%s", len(comments))

    positive_comments = 0
    neutral_comments = 0
    negative_comments = 0
    risk_keywords: list[str] = []
    priority_comments: list[dict[str, Any]] = []

    for comment in comments:
        rating = int(comment.get("rating", 0))
        content = str(comment.get("content", ""))
        keywords = _comment_risk_keywords(content)

        if rating >= 4:
            positive_comments += 1
        elif rating == 3:
            neutral_comments += 1
        else:
            negative_comments += 1

        if rating <= 2 or keywords:
            risk_keywords.extend(keywords)
            if not comment.get("replied", False):
                priority_comments.append(comment)

    unique_keywords = list(dict.fromkeys(risk_keywords))
    if negative_comments >= 2 or len(priority_comments) >= 3:
        risk_level = "high"
    elif negative_comments >= 1 or unique_keywords:
        risk_level = "medium"
    else:
        risk_level = "low"

    summary = {
        "total_comments": len(comments),
        "positive_comments": positive_comments,
        "neutral_comments": neutral_comments,
        "negative_comments": negative_comments,
        "risk_level": risk_level,
        "risk_keywords": unique_keywords,
    }

    suggestions = generate_mock_suggestions("reputation", summary)
    logger.info(
        "ReputationAgent finished risk_level=%s negative_comments=%s keywords=%s",
        risk_level,
        negative_comments,
        ",".join(unique_keywords) if unique_keywords else "none",
    )

    return {
        "agent": "舆情监控虾",
        "summary": summary,
        "priority_comments": priority_comments,
        "suggestions": suggestions,
        "ai_mode": get_ai_mode(),
    }
