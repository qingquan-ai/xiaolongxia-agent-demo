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
    llm_mode: str = os.getenv("LLM_MODE", "mock").lower()
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_model: str = os.getenv("LLM_MODEL", "mock-xiaolongxia-operator")

    @property
    def is_mock_mode(self) -> bool:
        return self.llm_mode == "mock" or not self.llm_api_key


settings = Settings()
