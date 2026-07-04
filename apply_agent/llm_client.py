from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import CONFIG, OUTPUTS_DIR
from .storage import ensure_dirs


class LLMClient:
    def __init__(self) -> None:
        ensure_dirs()
        self.api_key = CONFIG.deepseek_api_key
        self.base_url = CONFIG.deepseek_base_url
        self.model = CONFIG.deepseek_model
        self.log_path = OUTPUTS_DIR / "logs" / "llm_calls.jsonl"
        self.parse_error_dir = OUTPUTS_DIR / "logs" / "json_parse_errors"
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _append_log(self, payload: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _dump_response(self, response: Any) -> Any:
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if isinstance(response, dict):
            return response
        return str(response)

    def _extract_text(self, response: Any) -> str:
        if hasattr(response, "output_text") and getattr(response, "output_text"):
            return str(response.output_text)
        if hasattr(response, "output"):
            try:
                chunks: list[str] = []
                for item in response.output:
                    for content in getattr(item, "content", []) or []:
                        text = getattr(content, "text", None)
                        if text:
                            chunks.append(str(text))
                if chunks:
                    return "\n".join(chunks)
            except Exception:
                pass
        return str(response)

    def call_text(self, system_prompt: str, user_prompt: str) -> str:
        if self.client is None:
            raise RuntimeError("LLM client is not configured. Set DEEPSEEK_API_KEY in .env.")
        request_args: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        }
        if CONFIG.deepseek_enable_web_search:
            request_args["tools"] = [{"type": "web_search", "max_keyword": 3}]

        request_payload = {
            "timestamp": datetime.now().isoformat(),
            "kind": "text",
            "model": self.model,
            "base_url": self.base_url,
            "web_search_enabled": CONFIG.deepseek_enable_web_search,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
        try:
            response = self.client.responses.create(**request_args)
            response_text = self._extract_text(response)
            self._append_log({**request_payload, "response": self._dump_response(response), "response_text": response_text})
            return response_text
        except Exception as exc:
            self._append_log({**request_payload, "error": str(exc)})
            raise

    def _strip_json_fence(self, text: str) -> str:
        candidate = text.strip()
        fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.S | re.I)
        if fence_match:
            return fence_match.group(1).strip()
        return candidate

    def call_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raw_text = self.call_text(system_prompt, user_prompt)
        candidate = self._strip_json_fence(raw_text)
        try:
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                raise ValueError("LLM returned JSON but not as an object")
            return parsed
        except Exception as exc:
            self.parse_error_dir.mkdir(parents=True, exist_ok=True)
            error_file = self.parse_error_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_json_parse_error.txt"
            error_file.write_text(raw_text, encoding="utf-8")
            raise ValueError(f"Failed to parse model JSON output: {exc}. Raw output saved to {error_file}") from exc
