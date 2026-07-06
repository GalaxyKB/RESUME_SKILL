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

    def call_with_tools(self,
                        system_prompt: str,
                        user_prompt: str,
                        tools: list[dict]) -> list[dict] | str:
        """带工具定义的 LLM 调用。
        
        参数:
            tools: 格式 [{name, description, inputSchema}]
        
        返回:
            list[dict] — LLM 要调用的工具列表，每项 {name, arguments}
            str — LLM 直接回复文本（如 "done"）
        """
        return self._call_with_tools_fallback(system_prompt, user_prompt, tools)

    def _call_with_tools_fallback(self,
                                  system_prompt: str,
                                  user_prompt: str,
                                  tools: list[dict]) -> list[dict] | str:
        """通用回退方案：将 tools 定义序列化为文本嵌入 system_prompt。
        
        适用于不支持原生 function calling 的 API。
        """
        import json
        
        # 把 tools 转为 LLM 易读的文本格式
        tool_lines = []
        for t in tools:
            name = t["name"]
            desc = t.get("description", "")
            params = t.get("inputSchema", {}).get("properties", {})
            required = t.get("inputSchema", {}).get("required", [])
            
            param_lines = []
            for pname, pinfo in params.items():
                req_mark = " [必填]" if pname in required else ""
                param_lines.append(f"    {pname} ({pinfo.get('type', 'string')}): {pinfo.get('description', '')}{req_mark}")
            
            param_str = "\n".join(param_lines)
            tool_lines.append(f"- {name}: {desc}\n{param_str}")
        
        tools_text = "\n".join(tool_lines)
        
        enhanced_prompt = (system_prompt
                          + "\n\n## 可用工具\n"
                          + tools_text
                          + "\n\n每次回复格式：{\"tool\": \"tool_name\", \"params\": {...}, \"reason\": \"为什么\"}"
                          + "\n完成后回复：{\"tool\": \"done\", \"params\": {}}"
                          + "\n只输出 JSON，不要输出其他内容。")
        
        raw = self.call_text(enhanced_prompt, user_prompt)
        
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [{"name": item["tool"], "arguments": item.get("params", {})}
                       for item in parsed]
            
            tool_name = parsed.get("tool", "")
            if tool_name == "done":
                return "done"
            
            return [{"name": tool_name, "arguments": parsed.get("params", {})}]
        except json.JSONDecodeError:
            return raw

    @property
    def supports_function_calling(self) -> bool:
        """此 provider 是否支持原生 function calling API。"""
        return False  # 默认不支持，子类重写
