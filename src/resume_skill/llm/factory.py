from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import AppConfig, CONFIG
from .ark_provider import ArkResponsesProvider
from .base import BaseLLMClient
from .deepseek_provider import DeepSeekProvider
from .openai_provider import OpenAIProvider


def create_llm_client(config: AppConfig | None = None, outputs_dir: Path | None = None) -> BaseLLMClient:
    cfg = config or CONFIG
    log_dir = outputs_dir or cfg.outputs_dir / "logs"
    log_path = log_dir / "llm_calls.jsonl"
    parse_error_dir = log_dir / "json_parse_errors"

    provider = cfg.llm.provider.lower()

    if provider in {"ark", "doubao", "volcengine"}:
        if not cfg.llm.ark_api_key:
            raise RuntimeError("Ark API key not configured. Set ARK_API_KEY in .env.")
        return ArkResponsesProvider(
            api_key=cfg.llm.ark_api_key,
            base_url=cfg.llm.ark_base_url,
            model=cfg.llm.ark_model,
            log_path=log_path,
            parse_error_dir=parse_error_dir,
        )

    if provider == "openai":
        if not cfg.llm.openai_api_key:
            raise RuntimeError("OpenAI API key not configured. Set OPENAI_API_KEY in .env.")
        return OpenAIProvider(
            api_key=cfg.llm.openai_api_key,
            base_url=cfg.llm.openai_base_url,
            model=cfg.llm.openai_model,
            log_path=log_path,
            parse_error_dir=parse_error_dir,
        )

    if provider == "deepseek":
        if not cfg.llm.deepseek_api_key:
            raise RuntimeError("DeepSeek API key not configured. Set DEEPSEEK_API_KEY in .env.")
        return DeepSeekProvider(
            api_key=cfg.llm.deepseek_api_key,
            base_url=cfg.llm.deepseek_base_url,
            model=cfg.llm.deepseek_model,
            enable_web_search=cfg.llm.deepseek_enable_web_search,
            log_path=log_path,
            parse_error_dir=parse_error_dir,
        )

    if cfg.llm.deepseek_api_key:
        return DeepSeekProvider(
            api_key=cfg.llm.deepseek_api_key,
            base_url=cfg.llm.deepseek_base_url,
            model=cfg.llm.deepseek_model,
            enable_web_search=cfg.llm.deepseek_enable_web_search,
            log_path=log_path,
            parse_error_dir=parse_error_dir,
        )

    if cfg.llm.openai_api_key:
        return OpenAIProvider(
            api_key=cfg.llm.openai_api_key,
            base_url=cfg.llm.openai_base_url,
            model=cfg.llm.openai_model,
            log_path=log_path,
            parse_error_dir=parse_error_dir,
        )

    raise RuntimeError(
        "No LLM API key configured. Set DEEPSEEK_API_KEY or OPENAI_API_KEY in .env"
    )
