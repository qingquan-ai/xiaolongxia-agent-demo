import logging
from typing import Any, Callable

from app.core.config import settings
from app.services.feishu_bitable_service import read_bitable_records
from app.services.feishu_bitable_transformer import (
    convert_comment_records,
    convert_competitor_records,
    convert_order_records,
)
from app.services.json_store import load_comments, load_competitors, load_orders


logger = logging.getLogger(__name__)

DATA_SOURCE_JSON = "json"
DATA_SOURCE_FEISHU_BITABLE = "feishu_bitable"
SUPPORTED_DATA_SOURCES = {DATA_SOURCE_JSON, DATA_SOURCE_FEISHU_BITABLE}


def _current_data_source() -> str:
    data_source = getattr(settings, "data_source", DATA_SOURCE_JSON)
    data_source = str(data_source or "").strip().lower()
    if data_source in SUPPORTED_DATA_SOURCES:
        return data_source

    logger.warning(
        "Data source invalid value=%s fallback=json",
        data_source or "missing",
    )
    return DATA_SOURCE_JSON


def _load_feishu_bitable_data(
    *,
    table_name: str,
    converter: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    json_loader: Callable[[], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    try:
        raw_result = read_bitable_records(table_name)
    except Exception as exc:
        logger.warning(
            "Data source fallback=json source=feishu_bitable table=%s reason=read_exception error_type=%s",
            table_name,
            exc.__class__.__name__,
        )
        return json_loader()

    if not isinstance(raw_result, dict) or not raw_result.get("ok"):
        error = raw_result.get("error") if isinstance(raw_result, dict) else "invalid"
        logger.warning(
            "Data source fallback=json source=feishu_bitable table=%s reason=read_failed error=%s",
            table_name,
            error or "unknown",
        )
        return json_loader()

    raw_records = raw_result.get("records")
    raw_records = raw_records if isinstance(raw_records, list) else []
    try:
        converted_records = converter(raw_records)
    except Exception as exc:
        logger.warning(
            "Data source fallback=json source=feishu_bitable table=%s reason=convert_exception error_type=%s",
            table_name,
            exc.__class__.__name__,
        )
        return json_loader()

    if not converted_records:
        logger.warning(
            "Data source fallback=json source=feishu_bitable table=%s reason=empty_converted records=%s",
            table_name,
            len(raw_records),
        )
        return json_loader()

    logger.info(
        "Data source loaded source=feishu_bitable table=%s raw_records=%s converted_records=%s",
        table_name,
        len(raw_records),
        len(converted_records),
    )
    return converted_records


def load_orders_data() -> list[dict[str, Any]]:
    if _current_data_source() != DATA_SOURCE_FEISHU_BITABLE:
        return load_orders()
    return _load_feishu_bitable_data(
        table_name="orders",
        converter=convert_order_records,
        json_loader=load_orders,
    )


def load_comments_data() -> list[dict[str, Any]]:
    if _current_data_source() != DATA_SOURCE_FEISHU_BITABLE:
        return load_comments()
    return _load_feishu_bitable_data(
        table_name="comments",
        converter=convert_comment_records,
        json_loader=load_comments,
    )


def load_competitors_data() -> list[dict[str, Any]]:
    if _current_data_source() != DATA_SOURCE_FEISHU_BITABLE:
        return load_competitors()
    return _load_feishu_bitable_data(
        table_name="competitors",
        converter=convert_competitor_records,
        json_loader=load_competitors,
    )
