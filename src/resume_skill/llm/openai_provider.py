from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import httpx

from .base import BaseLLMClient


class OpenAIProvider(BaseLLMClient):
    """OpenAI-compatible provider using httpx (works with openai>=0.27 and custom endpoints)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o",
        log_path: Any = None,
        parse_error_dir: Any = None,
    ) -> None:
        super().__init__(log_path=log_path, parse_error_dir=parse_error_dir)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def call_text(self, system_prompt: str, user_prompt: str) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        log_payload = {
            "timestamp": datetime.now().isoformat(),
            "provider": "openai",
            "model": self.model,
            "system_prompt": system_prompt[:200],
            "user_prompt": user_prompt[:200],
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            request_body = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.3,
                "stream": False,
            }
            url = f"{self.base_url}/chat/completions"

            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, headers=headers, json=request_body)
                response.raise_for_status()
                data = response.json()

            text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            self._append_log({**log_payload, "response_text": text[:500]})
            return text
        except Exception as exc:
            self._append_log({**log_payload, "error": str(exc)})
            raise

    @property
    def supports_function_calling(self) -> bool:
        return True

    def call_with_tools(self,
                        system_prompt: str,
                        user_prompt: str,
                        tools: list[dict]) -> list[dict] | str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        # 转换为 OpenAI tools 格式
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {}),
                }
            })

        request_body = {
            "model": self.model,
            "messages": messages,
            "tools": openai_tools,
            "tool_choice": "auto",
            "temperature": 0.3,
            "stream": False,
        }

        log_payload = {
            "timestamp": datetime.now().isoformat(),
            "provider": "openai",
            "model": self.model,
            "tool_count": len(tools),
            "user_prompt": user_prompt[:200],
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            url = f"{self.base_url}/chat/completions"

            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, headers=headers, json=request_body)
                response.raise_for_status()
                data = response.json()

            msg = data.get("choices", [{}])[0].get("message", {})

            # 检查是否有 tool_calls
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                result = []
                for tc in tool_calls:
                    result.append({
                        "name": tc["function"]["name"],
                        "arguments": json.loads(tc["function"]["arguments"]),
                    })
                self._append_log({**log_payload, "tool_calls": [r["name"] for r in result]})
                return result

            # 直接回复文本
            content = msg.get("content", "")
            self._append_log({**log_payload, "response_text": content[:500]})
            return content

        except Exception as exc:
            self._append_log({**log_payload, "error": str(exc)})
            raise
