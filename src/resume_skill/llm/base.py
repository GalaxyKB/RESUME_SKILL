from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any


class BaseLLMClient(ABC):
    def __init__(self, log_path: Path | None = None, parse_error_dir: Path | None = None) -> None:
        self.log_path = log_path
        self.parse_error_dir = parse_error_dir

    def _append_log(self, payload: dict[str, Any]) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _save_parse_error(self, raw_text: str) -> None:
        if not self.parse_error_dir:
            return
        self.parse_error_dir.mkdir(parents=True, exist_ok=True)
        error_file = self.parse_error_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_json_parse_error.txt"
        error_file.write_text(raw_text, encoding="utf-8")

    @abstractmethod
    def call_text(self, system_prompt: str, user_prompt: str) -> str:
        ...

    def call_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raw_text = self.call_text(system_prompt, user_prompt)
        candidate = self._strip_json_fence(raw_text)
        try:
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                raise ValueError("LLM returned JSON but not as an object")
            return parsed
        except Exception as exc:
            self._save_parse_error(raw_text)
            raise ValueError(f"Failed to parse model JSON output: {exc}") from exc

    @staticmethod
    def _strip_json_fence(text: str) -> str:
        candidate = text.strip()
        fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.S | re.I)
        if fence_match:
            return fence_match.group(1).strip()
        json_match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if json_match:
            return json_match.group()
        return candidate
