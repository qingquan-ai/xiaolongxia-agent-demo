import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class Settings:
    app_name: str = "小龙虾 AI 自动运营中控台 Demo"
    app_version: str = "0.1.0"
    data_dir: Path = PROJECT_ROOT / "data"
    data_source: str = os.getenv("DATA_SOURCE", "json").strip().lower()
    llm_mode: str = os.getenv("LLM_MODE", "mock").strip().lower()
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "").strip()
    openrouter_base_url: str = (
        os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    ).rstrip("/")
    openrouter_model: str = (
        os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
    )
    llm_timeout_seconds: float = 20.0
    feishu_verification_token: str = os.getenv(
        "FEISHU_VERIFICATION_TOKEN",
        "",
    ).strip()
    cron_secret: str = os.getenv("CRON_SECRET", "").strip()
    debug_api_secret: str = os.getenv("DEBUG_API_SECRET", "").strip()
    feishu_app_id: str = os.getenv("FEISHU_APP_ID", "").strip()
    feishu_app_secret: str = os.getenv("FEISHU_APP_SECRET", "").strip()
    feishu_bitable_app_token: str = os.getenv(
        "FEISHU_BITABLE_APP_TOKEN",
        "",
    ).strip()
    feishu_orders_table_id: str = os.getenv("FEISHU_ORDERS_TABLE_ID", "").strip()
    feishu_comments_table_id: str = os.getenv(
        "FEISHU_COMMENTS_TABLE_ID",
        "",
    ).strip()
    feishu_competitors_table_id: str = os.getenv(
        "FEISHU_COMPETITORS_TABLE_ID",
        "",
    ).strip()

    @property
    def is_openrouter_enabled(self) -> bool:
        return self.llm_mode == "openrouter" and bool(self.openrouter_api_key)

    @property
    def is_mock_mode(self) -> bool:
        return not self.is_openrouter_enabled


settings = Settings()
