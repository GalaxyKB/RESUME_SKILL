from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx

from .base import BaseLLMClient


class DeepSeekProvider(BaseLLMClient):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        model: str = "deepseek-v4-pro-260425",
        enable_web_search: bool = False,
        log_path: Any = None,
        parse_error_dir: Any = None,
    ) -> None:
        super().__init__(log_path=log_path, parse_error_dir=parse_error_dir)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.enable_web_search = enable_web_search

    def call_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("DeepSeek API key not configured. Set DEEPSEEK_API_KEY in .env.")

        input_messages = []
        if system_prompt:
            input_messages.append({
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            })
        input_messages.append({
            "role": "user",
            "content": [{"type": "input_text", "text": user_prompt}],
        })

        request_body: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "input": input_messages,
        }

        if self.enable_web_search:
            request_body["tools"] = [{"type": "web_search", "max_keyword": 3}]

        log_payload = {
            "timestamp": datetime.now().isoformat(),
            "provider": "deepseek",
            "model": self.model,
            "system_prompt": system_prompt[:200],
            "user_prompt": user_prompt[:200],
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            url = f"{self.base_url}/responses"

            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, headers=headers, json=request_body)
                response.raise_for_status()
                response_data = response.json()

            response_text = self._extract_text_from_response(response_data)
            self._append_log({**log_payload, "response_text": response_text[:500]})
            return response_text
        except Exception as exc:
            self._append_log({**log_payload, "error": str(exc)})
            raise

    def _extract_text_from_response(self, response_data: dict) -> str:
        try:
            if "output" in response_data:
                for item in response_data["output"]:
                    if item.get("type") == "message" and item.get("role") == "assistant":
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                return content.get("text", "")
            if "choices" in response_data:
                for choice in response_data["choices"]:
                    delta = choice.get("message", choice.get("delta", {}))
                    content = delta.get("content", "")
                    if content:
                        return content
            return str(response_data)
        except Exception:
            return str(response_data)

    def call_with_tools(self,
                        system_prompt: str,
                        user_prompt: str,
                        tools: list[dict]) -> list[dict] | str:
        """火山引擎 ARK 的 /responses API 不支持标准 function calling。
        
        使用父类的文本回退方案。
        """
        return self._call_with_tools_fallback(system_prompt, user_prompt, tools)
