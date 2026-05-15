import json
import logging
import os
from pathlib import Path
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)

LATEST_REPORT_FILE = "latest_report.json"
LATEST_REPORT_DATA_VERSION = 1


def _safe_data_path(file_name: str) -> Path:
    data_dir = settings.data_dir.resolve()
    path = (data_dir / file_name).resolve()
    path.relative_to(data_dir)
    return path


def load_json_file(file_name: str) -> list[dict[str, Any]]:
    path = _safe_data_path(file_name)
    logger.info("Loading local JSON data file=%s", path.name)
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{file_name} must contain a JSON list")
    logger.info("Loaded JSON records file=%s count=%s", path.name, len(data))
    return data


def load_orders() -> list[dict[str, Any]]:
    return load_json_file("orders.json")


def load_comments() -> list[dict[str, Any]]:
    return load_json_file("comments.json")


def load_competitors() -> list[dict[str, Any]]:
    return load_json_file("competitors.json")


def _latest_report_cache_path() -> Path:
    return _safe_data_path(LATEST_REPORT_FILE)


def _validate_latest_report_cache(cache: Any) -> dict[str, Any]:
    if not isinstance(cache, dict):
        raise ValueError("not_dict")

    required_keys = ("order_analysis", "reputation_analysis", "competitors", "report")
    for key in required_keys:
        if key not in cache:
            raise ValueError(f"missing_{key}")

    report = cache["report"]
    if not isinstance(report, dict):
        raise ValueError("report_not_dict")
    for key in ("agent", "title", "markdown"):
        if key not in report:
            raise ValueError(f"missing_report_{key}")

    if not isinstance(cache["competitors"], list):
        raise ValueError("competitors_not_list")

    return cache


def load_latest_report_cache() -> dict[str, Any] | None:
    path = _latest_report_cache_path()
    if not path.exists():
        logger.info("Latest report cache invalid reason=missing")
        return None

    try:
        with path.open("r", encoding="utf-8") as file:
            cache = json.load(file)
        return _validate_latest_report_cache(cache)
    except json.JSONDecodeError:
        logger.warning("Latest report cache invalid reason=invalid_json")
    except OSError as exc:
        logger.warning(
            "Latest report cache invalid reason=read_error error_type=%s",
            exc.__class__.__name__,
        )
    except ValueError as exc:
        logger.warning("Latest report cache invalid reason=%s", exc)

    return None


def save_latest_report_cache(
    *,
    source: str,
    generated_at: str,
    order_analysis: dict[str, Any],
    reputation_analysis: dict[str, Any],
    competitors: list[dict[str, Any]],
    report: dict[str, Any],
) -> bool:
    cache_path = _latest_report_cache_path()
    tmp_path = _safe_data_path(f"{LATEST_REPORT_FILE}.tmp")
    payload = {
        "data_version": LATEST_REPORT_DATA_VERSION,
        "generated_at": generated_at,
        "source": source,
        "order_analysis": order_analysis,
        "reputation_analysis": reputation_analysis,
        "competitors": competitors,
        "report": report,
    }

    try:
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(tmp_path, cache_path)
    except (OSError, TypeError) as exc:
        logger.warning(
            "Latest report cache save failed source=%s error_type=%s",
            source,
            exc.__class__.__name__,
        )
        return False

    logger.info("Latest report cache saved source=%s", source)
    return True
