from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
import httpx

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

    def _append_log(self, payload: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _extract_text_from_response(self, response_data: dict) -> str:
        """Extract text from火山引擎 Responses API response."""
        try:
            # Response format: {"output": [{"type": "reasoning", ...}, {"type": "message", "content": [{"type": "output_text", "text": "..."}]}]}
            if "output" in response_data:
                for item in response_data["output"]:
                    if item.get("type") == "message" and item.get("role") == "assistant":
                        for content in item.get("content", []):
                            if content.get("type") == "output_text":
                                return content.get("text", "")
            
            # Fallback: return string representation
            return str(response_data)
        except Exception:
            return str(response_data)

    def call_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("LLM client is not configured. Set DEEPSEEK_API_KEY in .env.")
        
        # Build input messages
        input_messages = []
        if system_prompt:
            input_messages.append({
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}]
            })
        input_messages.append({
            "role": "user",
            "content": [{"type": "input_text", "text": user_prompt}]
        })
        
        request_body = {
            "model": self.model,
            "stream": False,
            "input": input_messages,
        }
        
        if CONFIG.deepseek_enable_web_search:
            request_body["tools"] = [{"type": "web_search", "max_keyword": 3}]

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
            # Use httpx to make the request
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
            self._append_log({**request_payload, "response": response_data, "response_text": response_text})
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
