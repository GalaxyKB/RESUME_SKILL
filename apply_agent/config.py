from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
RECORDS_DIR = PROJECT_ROOT / "records"

DEFAULT_DEEPSEEK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro-260425"


def _first_non_empty_env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key, "")
        if value and value.strip():
            return value.strip()
    return default


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> "AppConfig":
    # Force project .env values to avoid inheriting stale shell-level vars.
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    return AppConfig(
        deepseek_api_key=_first_non_empty_env("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL),
        deepseek_enable_web_search=_env_bool("DEEPSEEK_ENABLE_WEB_SEARCH", default=False),
    )


@dataclass(frozen=True)
class AppConfig:
    deepseek_api_key: str = ""
    deepseek_base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    deepseek_model: str = DEFAULT_DEEPSEEK_MODEL
    deepseek_enable_web_search: bool = False


CONFIG = load_config()
