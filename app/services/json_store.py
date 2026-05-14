import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import settings


logger = logging.getLogger(__name__)


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
