"""
Agent 执行记录器：记录每步决策、入参、结果，生成可读报告。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class AgentRecorder:
    def __init__(self):
        self._episode: list[dict] = []

    def record(self,
               step: int,
               phase: str,          # "deterministic" 或 "agent"
               tool: str,
               params: dict,
               result: Any,
               state_before: str,   # AgentState.to_prompt() 的返回值
               llm_reason: str = "",
               error: str = "",
               ) -> None:
        """记录一步执行。"""
        self._episode.append({
            "step": step,
            "phase": phase,
            "tool": tool,
            "params": params,
            "result": result,
            "state_before": state_before,
            "llm_reason": llm_reason,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })

    def save(self, filepath: str | Path) -> Path:
        """将完整 episode 保存为 JSON 文件。"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._episode, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def summary(self) -> str:
        """生成可打印的决策链文本。"""
        lines: list[str] = []
        lines.append("=" * 50)
        lines.append("MCP Agent 执行报告")
        lines.append("=" * 50)

        filled = sum(
            1 for s in self._episode
            if s["tool"] == "fill_field"
            and s["result"]
            and isinstance(s["result"], dict)
            and s["result"].get("status") == "filled"
        )
        failed = sum(
            1 for s in self._episode
            if s["tool"] == "fill_field"
            and s["result"]
            and isinstance(s["result"], dict)
            and s["result"].get("status") == "failed"
        )

        lines.append(f"总步数: {len(self._episode)}")
        lines.append(f"填充: {filled} 成功 / {failed} 失败")
        lines.append("")

        lines.append("决策链:")
        for s in self._episode:
            icon = "✅" if not s["error"] else "❌"
            tool_short = s["tool"]
            params_short = json.dumps(s["params"], ensure_ascii=False)[:60]
            lines.append(f"  Step {s['step']}: {icon} {tool_short}({params_short})")
            if s["llm_reason"]:
                lines.append(f"    理由: {s['llm_reason']}")

        return "\n".join(lines)