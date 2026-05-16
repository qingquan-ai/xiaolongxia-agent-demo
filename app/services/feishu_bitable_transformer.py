from datetime import datetime, timezone
from typing import Any


DEFAULT_STORE_NAME = "小龙虾人民广场店"
PERIOD_DEFAULT_TIMES = {
    "午市": "12:00:00",
    "晚市": "18:30:00",
    "夜宵": "22:00:00",
}
TRUE_STATUS_VALUES = {"已回复", "已处理", "已解决", "true", "是"}


def _get_fields(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    fields = record.get("fields")
    return fields if isinstance(fields, dict) else {}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [_to_text(item) for item in value]
        return "、".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "name", "value"):
            if key in value:
                return _to_text(value.get(key))
        return str(value).strip()
    return str(value).strip()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = _to_text(value)
        if not text:
            return default
        return int(float(text))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        text = _to_text(value)
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def _to_bool_status(value: Any) -> bool:
    return _to_text(value).lower() in TRUE_STATUS_VALUES


def _normalize_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
        except (OSError, OverflowError, ValueError):
            return ""

    text = _to_text(value)
    if not text:
        return ""

    normalized = text.replace("/", "-")
    if len(normalized) >= 10:
        normalized = normalized[:10]
    try:
        return datetime.strptime(normalized, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def _build_datetime(date_value: Any, period: Any = None) -> str:
    normalized_date = _normalize_date(date_value)
    if not normalized_date:
        return ""
    period_text = _to_text(period)
    time_text = PERIOD_DEFAULT_TIMES.get(period_text, "12:00:00")
    return f"{normalized_date} {time_text}"


def _record_id(record: Any, fallback_prefix: str, index: int) -> str:
    if isinstance(record, dict):
        record_id = _to_text(record.get("record_id"))
        if record_id:
            return record_id
    return f"{fallback_prefix}-{index}"


def _clean_amount(value: float) -> int | float:
    return int(value) if value.is_integer() else round(value, 2)


def convert_order_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        fields = _get_fields(record)
        if not fields:
            continue

        order_date = _normalize_date(fields.get("日期"))
        order_count = _to_int(fields.get("订单数"), default=0)
        total_revenue = _to_float(fields.get("销售额"), default=0.0)
        average_order_value = _to_float(fields.get("客单价"), default=0.0)
        if not order_date or order_count <= 0:
            continue

        if total_revenue > 0:
            amount = total_revenue / order_count
        elif average_order_value > 0:
            amount = average_order_value
        else:
            continue

        base_record_id = _record_id(record, "order", record_index)
        channel = _to_text(fields.get("平台")) or "未知渠道"
        product = _to_text(fields.get("爆款产品")) or "未知产品"
        note = _to_text(fields.get("备注"))
        order_time = _build_datetime(fields.get("日期"), fields.get("时段"))
        for item_index in range(1, order_count + 1):
            order = {
                "order_id": f"{base_record_id}-{item_index}",
                "store": DEFAULT_STORE_NAME,
                "channel": channel,
                "product": product,
                "quantity": 1,
                "amount": _clean_amount(amount),
                "order_time": order_time,
                "status": "completed",
            }
            if note:
                order["note"] = note
            converted.append(order)
    return converted


def convert_comment_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        fields = _get_fields(record)
        if not fields:
            continue

        content = _to_text(fields.get("评论内容"))
        if not content:
            continue

        created_at = _build_datetime(fields.get("日期"))
        comment = {
            "comment_id": _record_id(record, "comment", record_index),
            "platform": _to_text(fields.get("平台")) or "未知平台",
            "store": DEFAULT_STORE_NAME,
            "rating": _to_int(fields.get("评分"), default=0),
            "content": content,
            "created_at": created_at,
            "replied": _to_bool_status(fields.get("处理状态")),
        }
        note = _to_text(fields.get("备注"))
        if note:
            comment["note"] = note
        converted.append(comment)
    return converted


def convert_competitor_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        fields = _get_fields(record)
        if not fields:
            continue

        name = _to_text(fields.get("竞品门店"))
        promotion = _to_text(fields.get("促销动作"))
        hot_product = _to_text(fields.get("热卖品"))
        if not name or (not promotion and not hot_product):
            continue

        competitor = {
            "name": name,
            "platform": _to_text(fields.get("平台")) or "未知平台",
            "promotion": promotion or "暂无促销",
            "hot_product": hot_product or "未知产品",
            "rating": 0,
            "note": _to_text(fields.get("备注")),
            "record_id": _record_id(record, "competitor", record_index),
        }
        date_text = _normalize_date(fields.get("日期"))
        if date_text:
            competitor["date"] = date_text
        converted.append(competitor)
    return converted


def convert_bitable_records(
    table_name: str,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if table_name == "orders":
        return convert_order_records(records)
    if table_name == "comments":
        return convert_comment_records(records)
    if table_name == "competitors":
        return convert_competitor_records(records)
    return []
