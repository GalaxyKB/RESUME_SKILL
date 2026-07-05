from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

import yaml


def _get_project_root() -> Path:
    """
    Get project root directory, handling both development and pip installation modes.
    Priority: RESUME_SKILL_ROOT env var > current working directory
    """
    # First try environment variable
    env_root = os.getenv("RESUME_SKILL_ROOT")
    if env_root:
        return Path(env_root).resolve()
    
    # For development mode (pip install -e .)
    # __file__ points to source code directory
    source_root = Path(__file__).resolve().parent.parent.parent
    if (source_root / "pyproject.toml").exists():
        return source_root
    
    # For pip installation or unknown environment
    # Fall back to current working directory
    return Path.cwd()


PROJECT_ROOT = _get_project_root()

DEFAULT_DEEPSEEK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-pro-260425"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o"


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class LLMConfig:
    provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    deepseek_model: str = DEFAULT_DEEPSEEK_MODEL
    deepseek_enable_web_search: bool = False
    openai_api_key: str = ""
    openai_base_url: str = DEFAULT_OPENAI_BASE_URL
    openai_model: str = DEFAULT_OPENAI_MODEL


@dataclass
class BrowserConfig:
    headless: bool = False
    slow_motion: int = 300
    launch_timeout: int = 30000
    navigation_timeout: int = 60000
    browser_channel: str = "chrome"
    browser_executable_path: str = ""
    locale: str = "zh-CN"
    timezone_id: str = "Asia/Shanghai"
    viewport_width: int = 1920
    viewport_height: int = 1080


@dataclass
class FormFillingConfig:
    auto_fill: bool = True
    require_confirmation: bool = True
    max_extraction_retries: int = 8
    extraction_retry_delay: int = 1200
    fill_operation_timeout: int = 30000
    inter_field_delay: int = 100
    auto_submit: bool = False
    submit_wait_time: int = 2000
    max_fill_rounds: int = 5


@dataclass
class StorageConfig:
    profile_dir: str = ""
    outputs_dir: str = ""
    records_dir: str = ""
    session_dir: str = ""


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    form_filling: FormFillingConfig = field(default_factory=FormFillingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    debug_mode: bool = False
    log_level: str = "INFO"
    _project_root: Path = field(default_factory=_get_project_root)

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def personal_info_dir(self) -> Path:
        if self.storage.profile_dir:
            return Path(self.storage.profile_dir)
        return self._project_root / "personal_info"

    @property
    def outputs_dir(self) -> Path:
        if self.storage.outputs_dir:
            return Path(self.storage.outputs_dir)
        return self._project_root / "outputs"

    @property
    def records_dir(self) -> Path:
        if self.storage.records_dir:
            return Path(self.storage.records_dir)
        return self._project_root / "records"

    @property
    def session_dir(self) -> Path:
        if self.storage.session_dir:
            return Path(self.storage.session_dir)
        return self._project_root / ".session" / "chrome"

    @property
    def unified_profile_path(self) -> Path:
        return self.personal_info_dir / "unified_profile.yaml"

    @property
    def resume_dir(self) -> Path:
        return self.personal_info_dir / "formal_resume"


def load_app_config(project_dir: Optional[Path] = None) -> AppConfig:
    # Use local project root instead of modifying global
    root = project_dir or _get_project_root()

    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)

    config_yaml_path = root / "config.yaml"
    yaml_data: dict[str, Any] = {}
    if config_yaml_path.exists():
        with open(config_yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}

    llm_cfg = LLMConfig(
        provider=_env("LLM_PROVIDER", yaml_data.get("api", {}).get("provider", "deepseek")),
        deepseek_api_key=_env("DEEPSEEK_API_KEY"),
        deepseek_base_url=_env("DEEPSEEK_BASE_URL", yaml_data.get("api", {}).get("deepseek_base_url", DEFAULT_DEEPSEEK_BASE_URL)),
        deepseek_model=_env("DEEPSEEK_MODEL", yaml_data.get("api", {}).get("deepseek_model", DEFAULT_DEEPSEEK_MODEL)),
        deepseek_enable_web_search=_env_bool("DEEPSEEK_ENABLE_WEB_SEARCH", yaml_data.get("api", {}).get("deepseek_enable_web_search", False)),
        openai_api_key=_env("OPENAI_API_KEY"),
        openai_base_url=_env("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
        openai_model=_env("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
    )

    browser_yaml = yaml_data.get("browser", {})
    browser_cfg = BrowserConfig(
        headless=_env_bool("BROWSER_HEADLESS", browser_yaml.get("headless", False)),
        slow_motion=int(_env("BROWSER_SLOW_MOTION", str(browser_yaml.get("slow_motion", 300)))),
        launch_timeout=browser_yaml.get("launch_timeout", 30000),
        navigation_timeout=browser_yaml.get("navigation_timeout", 60000),
        browser_channel=_env("BROWSER_CHANNEL", browser_yaml.get("channel", "chrome")),
        browser_executable_path=_env("BROWSER_EXECUTABLE_PATH", browser_yaml.get("executable_path", "")),
        locale=browser_yaml.get("locale", "zh-CN"),
        timezone_id=browser_yaml.get("timezone_id", "Asia/Shanghai"),
        viewport_width=browser_yaml.get("viewport", {}).get("width", 1920),
        viewport_height=browser_yaml.get("viewport", {}).get("height", 1080),
    )

    fill_yaml = yaml_data.get("form_filling", {})
    form_cfg = FormFillingConfig(
        auto_fill=fill_yaml.get("auto_fill", True),
        require_confirmation=fill_yaml.get("require_confirmation_before_fill", True),
        max_extraction_retries=fill_yaml.get("max_extraction_retries", 8),
        extraction_retry_delay=fill_yaml.get("extraction_retry_delay", 1200),
        fill_operation_timeout=fill_yaml.get("fill_operation_timeout", 30000),
        inter_field_delay=fill_yaml.get("inter_field_delay", 100),
        auto_submit=fill_yaml.get("auto_submit", False),
        submit_wait_time=fill_yaml.get("submit_wait_time", 2000),
        max_fill_rounds=fill_yaml.get("max_fill_rounds", 5),
    )

    storage_yaml = yaml_data.get("storage", {})
    storage_cfg = StorageConfig(
        profile_dir=storage_yaml.get("profile_dir", ""),
        outputs_dir=storage_yaml.get("outputs_dir", ""),
        records_dir=storage_yaml.get("records_dir", ""),
        session_dir=storage_yaml.get("session_dir", ""),
    )

    return AppConfig(
        llm=llm_cfg,
        browser=browser_cfg,
        form_filling=form_cfg,
        storage=storage_cfg,
        debug_mode=_env_bool("DEBUG_MODE", yaml_data.get("advanced", {}).get("debug_mode", False)),
        log_level=_env("LOG_LEVEL", yaml_data.get("logging", {}).get("level", "INFO")),
        _project_root=root,  # Pass the root to AppConfig
    )


CONFIG = load_app_config()
