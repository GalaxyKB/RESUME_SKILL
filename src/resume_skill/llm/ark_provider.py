from __future__ import annotations

import base64
import time
from datetime import datetime
from typing import Any

import httpx

from .base import BaseLLMClient


class ArkResponsesProvider(BaseLLMClient):
    """Volcengine Ark /responses provider with text and image input support."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        model: str = "doubao-seed-2-0-lite-260428",
        log_path: Any = None,
        parse_error_dir: Any = None,
    ) -> None:
        super().__init__(log_path=log_path, parse_error_dir=parse_error_dir)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def call_text(self, system_prompt: str, user_prompt: str) -> str:
        content = []
        if system_prompt:
            content.append({"type": "input_text", "text": system_prompt})
        content.append({"type": "input_text", "text": user_prompt})
        return self._call_responses([{"role": "user", "content": content}], "text", user_prompt)

    def call_vision_text(self, prompt: str, image_bytes: bytes, mime_type: str = "image/png") -> str:
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        image_url = f"data:{mime_type};base64,{image_b64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_url},
                    {"type": "input_text", "text": prompt},
                ],
            }
        ]
        return self._call_responses(messages, "vision", prompt)

    def _call_responses(self, input_messages: list[dict], mode: str, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("Ark API key not configured. Set ARK_API_KEY or DEEPSEEK_API_KEY in .env.")

        request_body = {"model": self.model, "stream": False, "input": input_messages}
        log_payload = {
            "timestamp": datetime.now().isoformat(),
            "provider": "ark",
            "mode": mode,
            "model": self.model,
            "prompt": prompt[:200],
        }

        last_exc = None
        for attempt in range(3):
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                with httpx.Client(timeout=httpx.Timeout(90.0, connect=20.0, read=90.0, write=30.0)) as client:
                    response = client.post(f"{self.base_url}/responses", headers=headers, json=request_body)
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:800]}") from exc
                    data = response.json()
                text = self._extract_text_from_response(data)
                self._append_log({**log_payload, "response_text": text[:500], "attempt": attempt + 1})
                return text
            except Exception as exc:
                last_exc = exc
                self._append_log({**log_payload, "error": str(exc), "attempt": attempt + 1})
                if attempt < 2:
                    time.sleep(1.0 + attempt * 1.5)
        raise RuntimeError(f"Ark responses call failed after 3 attempts: {last_exc}") from last_exc

    @staticmethod
    def _extract_text_from_response(response_data: dict) -> str:
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


class ArkChatVisionProvider(BaseLLMClient):
    """Volcengine Ark chat/completions provider for image understanding."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        model: str = "doubao-seed-2-1-turbo-260628",
        log_path: Any = None,
        parse_error_dir: Any = None,
    ) -> None:
        super().__init__(log_path=log_path, parse_error_dir=parse_error_dir)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def call_text(self, system_prompt: str, user_prompt: str) -> str:
        content = user_prompt if not system_prompt else f"{system_prompt}\n\n{user_prompt}"
        messages = [{"role": "user", "content": content}]
        return self._call_chat(messages, "text", user_prompt)

    def call_vision_text(self, prompt: str, image_bytes: bytes, mime_type: str = "image/png") -> str:
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        image_url = f"data:{mime_type};base64,{image_b64}"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        return self._call_chat(messages, "vision", prompt)

    def _call_chat(self, messages: list[dict], mode: str, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("Ark API key not configured. Set VISION_API_KEY or ARK_API_KEY in .env.")

        request_body = {"model": self.model, "messages": messages}
        log_payload = {
            "timestamp": datetime.now().isoformat(),
            "provider": "ark_chat",
            "mode": mode,
            "model": self.model,
            "prompt": prompt[:200],
        }
        last_exc = None
        for attempt in range(3):
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                with httpx.Client(timeout=httpx.Timeout(90.0, connect=20.0, read=90.0, write=30.0)) as client:
                    response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=request_body)
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:800]}") from exc
                    data = response.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                self._append_log({**log_payload, "response_text": text[:500], "attempt": attempt + 1})
                return text
            except Exception as exc:
                last_exc = exc
                self._append_log({**log_payload, "error": str(exc), "attempt": attempt + 1})
                if attempt < 2:
                    time.sleep(1.0 + attempt * 1.5)
        raise RuntimeError(f"Ark chat call failed after 3 attempts: {last_exc}") from last_exc
