import logging
from typing import Any

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)

FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"
SOURCE_NAME = "feishu_bitable"
SUPPORTED_TABLE_NAMES = {"orders", "comments", "competitors"}


def _error_response(table_name: str, error: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "source": SOURCE_NAME,
        "table": table_name,
        "error": error,
        "message": message,
    }


def _table_id_for(table_name: str) -> str:
    table_id_map = {
        "orders": settings.feishu_orders_table_id,
        "comments": settings.feishu_comments_table_id,
        "competitors": settings.feishu_competitors_table_id,
    }
    return table_id_map.get(table_name, "")


def is_supported_bitable_table(table_name: str) -> bool:
    return table_name in SUPPORTED_TABLE_NAMES


def _missing_config(table_name: str) -> list[str]:
    missing = []
    if not settings.feishu_app_id:
        missing.append("FEISHU_APP_ID")
    if not settings.feishu_app_secret:
        missing.append("FEISHU_APP_SECRET")
    if not settings.feishu_bitable_app_token:
        missing.append("FEISHU_BITABLE_APP_TOKEN")
    if not _table_id_for(table_name):
        missing.append(f"FEISHU_{table_name.upper()}_TABLE_ID")
    return missing


def _get_tenant_access_token() -> str | None:
    url = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
    try:
        response = httpx.post(
            url,
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
            timeout=10.0,
        )
        body = response.json()
    except Exception as exc:
        logger.warning(
            "Feishu bitable token request failed error_type=%s",
            exc.__class__.__name__,
        )
        return None

    code = body.get("code") if isinstance(body, dict) else None
    token = body.get("tenant_access_token") if isinstance(body, dict) else None
    if response.status_code != 200 or code != 0 or not isinstance(token, str) or not token:
        logger.warning(
            "Feishu bitable token request failed status_code=%s code=%s",
            response.status_code,
            code,
        )
        return None
    return token


def _normalize_records(items: Any) -> list[dict[str, Any]]:
    records = []
    if not isinstance(items, list):
        return records

    for item in items:
        if not isinstance(item, dict):
            continue
        record_id = item.get("record_id")
        fields = item.get("fields")
        records.append(
            {
                "record_id": str(record_id) if record_id else "",
                "fields": fields if isinstance(fields, dict) else {},
            }
        )
    return records


def read_bitable_records(table_name: str, page_size: int = 20) -> dict[str, Any]:
    missing = _missing_config(table_name)
    if missing:
        logger.warning(
            "Feishu bitable debug failed table=%s reason=missing_config missing=%s",
            table_name,
            ",".join(missing),
        )
        return _error_response(
            table_name,
            "missing_config",
            "Missing Feishu bitable configuration.",
        )

    tenant_access_token = _get_tenant_access_token()
    if not tenant_access_token:
        return _error_response(
            table_name,
            "tenant_access_token_failed",
            "Failed to get Feishu tenant access token.",
        )

    table_id = _table_id_for(table_name)
    url = (
        f"{FEISHU_BASE_URL}/bitable/v1/apps/{settings.feishu_bitable_app_token}"
        f"/tables/{table_id}/records"
    )
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {tenant_access_token}"},
            params={"page_size": page_size},
            timeout=10.0,
        )
        body = response.json()
    except Exception as exc:
        logger.warning(
            "Feishu bitable records request failed table=%s error_type=%s",
            table_name,
            exc.__class__.__name__,
        )
        return _error_response(
            table_name,
            "bitable_records_fetch_failed",
            "Failed to fetch Feishu bitable records.",
        )

    code = body.get("code") if isinstance(body, dict) else None
    if response.status_code != 200 or code != 0:
        logger.warning(
            "Feishu bitable records request failed table=%s status_code=%s code=%s",
            table_name,
            response.status_code,
            code,
        )
        return _error_response(
            table_name,
            "bitable_records_fetch_failed",
            "Failed to fetch Feishu bitable records.",
        )

    data = body.get("data") if isinstance(body, dict) else {}
    items = data.get("items") if isinstance(data, dict) else []
    records = _normalize_records(items)
    return {
        "ok": True,
        "source": SOURCE_NAME,
        "table": table_name,
        "record_count": len(records),
        "records": records,
    }
