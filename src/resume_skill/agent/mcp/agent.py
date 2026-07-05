"""
LLM Agent: decision loop that replaces hardcoded workflow.py.

The Agent receives a list of available MCP tools and uses LLM function
calls to decide which tool to invoke at each step.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any

from ..llm.factory import create_llm_client
from ..llm.base import BaseLLMClient
from ..config import CONFIG
from .mcp.client import MCPClient
from .utils import load_yaml, print_section, console


@dataclass
class AgentState:
    step: int = 0
    page_url: str = ""
    field_count: int = 0
    filled_fields: list[dict] = field(default_factory=list)
    failed_fields: list[dict] = field(default_factory=list)
    verified_fields: list[dict] = field(default_factory=list)
    last_error: str = ""
    max_steps: int = 30
    consecutive_no_progress: int = 0
    
    def to_prompt(self) -> str:
        return json.dumps({
            "当前步骤": self.step,
            "页面URL": self.page_url,
            "已提取字段数": self.field_count,
            "已填充字段": [f["field_id"] for f in self.filled_fields],
            "填充失败字段": [f["field_id"] for f in self.failed_fields],
            "最后错误": self.last_error,
        }, ensure_ascii=False)


SYSTEM_PROMPT = """你是一个网申表单自动填充 Agent。

## 可用工具
{tool_descriptions}

## 用户数据
{profile_json}

## 推荐工作流程
1. browser_start → browser_navigate → wait_for_user（等待用户登录）
2. get_page_text（分析页面内容）
3. extract_fields（提取表单字段）
4. match_fields(fields_json, profile_json)（匹配字段与用户档案，得到填充计划）
5. 根据match_fields的结果，使用fill_field逐个填充字段
6. 使用verify_field验证已填充的字段
7. find_and_click提交表单
8. browser_close关闭浏览器

## 规则
- 每一步输出一个 JSON，格式：{{"tool": "tool_name", "params": {{...}}, "reason": "为什么"}}
- 如果所有步骤完成，输出：{{"tool": "done", "params": {{}}, "reason": "全部完成"}}
- 如果遇到需要用户手动处理的情况，输出：{{"tool": "wait_for_user", "params": {{"message": "提示内容"}}, "reason": "..."}}
- 优先使用match_fields工具进行字段匹配，而不是自己猜测如何填充

## 已执行的步骤
{history}

请决定下一步操作。只输出 JSON，不要输出其他内容。"""


def _build_tool_descriptions() -> str:
    from .mcp.server import TOOL_HELP
    lines = []
    for name, info in TOOL_HELP.items():
        params_desc = []
        for pname, pinfo in info.get("params", {}).items():
            required = "default" not in pinfo
            default_str = f" (默认: {pinfo.get('default')})" if "default" in pinfo else ""
            params_desc.append(f"    - {pname}: {pinfo.get('description', '')}{' [必填]' if required else default_str}")
        params_str = "\n".join(params_desc)
        lines.append(f"- {name}: {info.get('description', '')}\n{params_str}")
    return "\n".join(lines)


class MCPAgent:
    def __init__(self, llm_client: BaseLLMClient | None = None):
        self.client = MCPClient()
        self.llm = llm_client or create_llm_client()
        self.profile: dict[str, Any] = {}

    def _load_profile(self) -> dict[str, Any]:
        profile_path = CONFIG.unified_profile_path
        if profile_path.exists():
            return load_yaml(profile_path) or {}
        print(f"Profile not found at {profile_path}")
        return {}

    def run(self, url: str) -> None:
        print_section("MCP Agent - 智能填充流程")
        self.profile = self._load_profile()
        if not self.profile:
            console.print("[red]❌ 未找到用户档案，请先运行 resume-skill consolidate[/]")
            return

        tool_desc = _build_tool_descriptions()
        self.client.connect()
        state = AgentState()
        history: list[str] = []

        # Initial deterministic steps (no LLM needed)
        print("[Step 0] 启动浏览器...")
        self.client.call_tool("browser_start", {"session_dir": str(CONFIG.session_dir)})
        history.append("browser_start: 启动浏览器")
        
        print("[Step 1] 导航到目标页面...")
        self.client.call_tool("browser_navigate", {"url": url})
        history.append(f"browser_navigate: 导航到 {url}")
        
        print("[Step 2] 等待用户登录...")
        self.client.call_tool("wait_for_user", {"message": "请在浏览器中完成登录后按 Enter 继续..."})
        history.append("wait_for_user: 等待用户登录")

        # Agent loop with state management
        while state.step < state.max_steps:
            state.step += 1
            print(f"\n--- Step {state.step} ---")

            # Update state
            try:
                page_text = self.client.call_tool("get_page_text", {})
                state.page_url = self._get_current_url()
            except Exception as e:
                state.last_error = str(e)
                print(f"⚠️ 状态更新失败: {e}")

            # Build system prompt with history and state
            history_text = "\n".join([f"- {h}" for h in history[-10:]])  # Last 10 steps
            system_prompt = SYSTEM_PROMPT.format(
                tool_descriptions=tool_desc,
                profile_json=json.dumps(self.profile, ensure_ascii=False, indent=2),
                history=history_text
            )
            
            # Build user prompt with current state
            user_prompt = f"当前状态:\n{state.to_prompt()}\n\n请决定下一步操作。"

            # Call LLM
            response = self.llm.call_json(system_prompt, user_prompt)
            print(f"[LLM] {str(response)[:200]}...")

            # Parse tool call
            tool_call = self._parse_tool_call(response)
            if tool_call is None:
                console.print("[yellow]⚠️ LLM 返回格式无法解析[/]")
                state.last_error = "JSON解析失败"
                state.consecutive_no_progress += 1
                if state.consecutive_no_progress >= 3:
                    console.print("[red]连续3步无进展，终止[/]")
                    break
                continue

            tool_name, params = tool_call
            
            # Handle special tools
            if tool_name == "done":
                console.print("[green]✅ LLM判断任务完成[/]")
                break
                
            if tool_name == "wait_for_user":
                print(f"[等待用户] {params.get('message', '请操作后继续...')}")
                self.client.call_tool("wait_for_user", params)
                history.append(f"wait_for_user: {params.get('message', '等待用户操作')}")
                continue

            # Execute tool
            try:
                result = self.client.call_tool(tool_name, params)
                print(f"  → {tool_name} 返回: {json.dumps(result, ensure_ascii=False)[:200]}")
                
                # Update state based on result
                self._update_state(state, tool_name, params, result)
                history.append(f"{tool_name}: {params} → {result.get('status', 'unknown')}")
                state.consecutive_no_progress = 0  # Reset on success
                
            except Exception as e:
                print(f"  → {tool_name} 失败: {e}")
                state.last_error = str(e)
                state.consecutive_no_progress += 1
                history.append(f"{tool_name}: {params} → 失败: {e}")
                
                # Check for no progress
                if state.consecutive_no_progress >= 5:
                    console.print("[red]连续5步无进展，终止[/]")
                    break

        self.client.close()
        console.print("[green]✅ 填充流程完成[/]")

    def _get_current_url(self) -> str:
        """Get current page URL (helper method)."""
        try:
            result = self.client.call_tool("get_current_url", {})
            return result.get("url", "")
        except:
            return ""

    def _update_state(self, state: AgentState, tool_name: str, params: dict, result: dict) -> None:
        """Update agent state based on tool result."""
        if tool_name == "fill_field":
            if result.get("status") in ["filled", "verified"]:
                field_info = {
                    "field_id": params.get("field_id", ""),
                    "field_label": params.get("field_label", ""),
                    "status": result.get("status")
                }
                state.filled_fields.append(field_info)
            elif result.get("status") in ["failed", "error"]:
                field_info = {
                    "field_id": params.get("field_id", ""),
                    "field_label": params.get("field_label", ""),
                    "error": result.get("error", "")
                }
                state.failed_fields.append(field_info)
        elif tool_name == "extract_fields":
            # Update field count when extract_fields is called
            state.field_count = result.get("count", 0)
        elif tool_name == "verify_field":
            if result.get("verified"):
                field_info = {
                    "field_id": params.get("field_id", ""),
                    "field_label": params.get("field_label", ""),
                    "verified": True
                }
                state.verified_fields.append(field_info)

    def _parse_tool_call(self, response):
        """Parse tool call from LLM response (handles both dict and str)."""
        if isinstance(response, dict):
            return response.get("tool"), response.get("params", {})
        
        try:
            obj = json.loads(str(response))
            return obj.get("tool"), obj.get("params", {})
        except (json.JSONDecodeError, TypeError):
            return None


def run_agent(url: str) -> None:
    llm = create_llm_client()
    agent = MCPAgent(llm_client=llm)
    agent.run(url)
