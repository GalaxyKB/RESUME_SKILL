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

from ...llm.factory import create_llm_client
from ...llm.base import BaseLLMClient
from ...config import CONFIG
from .client import MCPClient
from ..utils import load_yaml, print_section, console
from .recorder import AgentRecorder


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
    from .server import TOOL_HELP
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
    def __init__(self, llm_client: BaseLLMClient | None = None, resume_from: str = ""):
        # 如果配置了 MCP_PYTHON_PATH，则自动使用 MCP SDK 模式
        use_sdk = bool(CONFIG.mcp.python_path)
        self.client = MCPClient(
            use_mcp_sdk=use_sdk,
            mcp_python_path=CONFIG.mcp.python_path
        )
        self.llm = llm_client or create_llm_client()
        self.profile: dict[str, Any] = {}
        self.recorder = AgentRecorder()
        self._resume_from = resume_from

    def _build_tools_for_api(self) -> list[dict]:
        """将 TOOL_HELP 转换为 LLM API 兼容的 tools 格式。"""
        from .server import TOOL_HELP
        
        tools = []
        for name, info in TOOL_HELP.items():
            params = info.get("params", {})
            properties = {}
            required = []
            
            for pname, pinfo in params.items():
                ptype = pinfo.get("type", "string")
                schema_type = "array" if ptype == "array" else "object" if ptype == "object" else "string"
                properties[pname] = {
                    "type": schema_type,
                    "description": pinfo.get("description", ""),
                }
                if "default" not in pinfo:
                    required.append(pname)
            
            tools.append({
                "name": name,
                "description": info.get("description", ""),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return tools

    def _load_profile(self) -> dict[str, Any]:
        profile_path = CONFIG.unified_profile_path
        if profile_path.exists():
            return load_yaml(profile_path) or {}
        print(f"Profile not found at {profile_path}")
        return {}

    def run(self, url: str, resume_from: str = "") -> None:
        print_section("MCP Agent - 智能填充流程")
        self._url = url
        self.profile = self._load_profile()
        if not self.profile:
            console.print("[red]❌ 未找到用户档案，请先运行 resume-skill consolidate[/]")
            return

        tool_desc = _build_tool_descriptions()
        self.client.connect()
        
        # 恢复 checkpoint 或初始化
        if resume_from:
            # 恢复 checkpoint
            checkpoint = self._load_checkpoint(resume_from)
            state = AgentState(**checkpoint["state"])
            history = checkpoint.get("history", [])
            deterministic_done = checkpoint.get("deterministic_done", [])
            console.print(f"[yellow]从 checkpoint 恢复: 已完成 {len(deterministic_done)} 个确定性步骤[/]")
        else:
            state = AgentState()
            history = []
            deterministic_done = []

        # Initial deterministic steps (no LLM needed)
        # 第一步：browser_start
        if "browser_start" not in deterministic_done:
            print("[Step 0] 启动浏览器...")
            browser_start_result = self.client.call_tool("browser_start", {"session_dir": str(CONFIG.session_dir)})
            self.recorder.record(step=0, phase="deterministic", tool="browser_start",
                                params={"session_dir": str(CONFIG.session_dir)},
                                result=browser_start_result, state_before="",
                                llm_reason="")
            history.append("browser_start: 启动浏览器")
            deterministic_done.append("browser_start")
            ckpt_path = self._save_checkpoint(state, history, deterministic_done)
            print(f"  Checkpoint 已保存: {ckpt_path}")
        else:
            print("[Step 0] 跳过 browser_start（已从 checkpoint 恢复）")
        
        # 第二步：browser_navigate
        if "browser_navigate" not in deterministic_done:
            print("[Step 1] 导航到目标页面...")
            browser_navigate_result = self.client.call_tool("browser_navigate", {"url": url})
            self.recorder.record(step=1, phase="deterministic", tool="browser_navigate",
                                params={"url": url},
                                result=browser_navigate_result, state_before="",
                                llm_reason="")
            history.append(f"browser_navigate: 导航到 {url}")
            deterministic_done.append("browser_navigate")
            ckpt_path = self._save_checkpoint(state, history, deterministic_done)
            print(f"  Checkpoint 已保存: {ckpt_path}")
        else:
            print("[Step 1] 跳过 browser_navigate（已从 checkpoint 恢复）")
        
        # 第三步：wait_for_user
        if "wait_for_user" not in deterministic_done:
            print("[Step 2] 等待用户登录...")
            wait_result = self.client.call_tool("wait_for_user", {"message": "请在浏览器中完成登录后按 Enter 继续..."})
            self.recorder.record(step=2, phase="deterministic", tool="wait_for_user",
                                params={"message": "请在浏览器中完成登录后按 Enter 继续..."},
                                result=wait_result, state_before="",
                                llm_reason="")
            history.append("wait_for_user: 等待用户登录")
            deterministic_done.append("wait_for_user")
            ckpt_path = self._save_checkpoint(state, history, deterministic_done)
            print(f"  Checkpoint 已保存: {ckpt_path}")
        else:
            print("[Step 2] 跳过 wait_for_user（已从 checkpoint 恢复）")

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

            # 保存执行前的状态
            state_before = state.to_prompt()

            # Call LLM
            # 构建工具列表
            tools = self._build_tools_for_api()
            
            if hasattr(self.llm, 'call_with_tools') and getattr(self.llm, 'supports_function_calling', False):
                # 原生 function calling 模式
                llm_result = self.llm.call_with_tools(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    tools=tools,
                )
                
                if isinstance(llm_result, list):
                    # LLM 返回了工具调用
                    tool_name = llm_result[0]["name"]
                    params = llm_result[0].get("arguments", {})
                    reason = ""
                    tool_call = (tool_name, params)
                elif isinstance(llm_result, str):
                    # LLM 直接回复文本
                    print(f"[LLM] {llm_result[:200]}...")
                    if "done" in llm_result.strip().lower():
                        console.print("[green]✅ LLM判断任务完成[/]")
                        break
                    tool_call = None
                else:
                    tool_call = None
            else:
                # 回退：call_json + 解析
                response = self.llm.call_json(system_prompt, user_prompt)
                print(f"[LLM] {str(response)[:200]}...")
                reason = response.get("reason", "") if isinstance(response, dict) else ""
                tool_call = self._parse_tool_call(response)

            # 解析 tool call（与原逻辑一致）
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
                wait_result = self.client.call_tool("wait_for_user", params)
                # 记录等待用户步骤
                self.recorder.record(step=state.step, phase="agent", tool=tool_name,
                                    params=params, result=wait_result,
                                    state_before=state_before, llm_reason=reason)
                history.append(f"wait_for_user: {params.get('message', '等待用户操作')}")
                continue

            # Execute tool
            try:
                result = self.client.call_tool(tool_name, params)
                print(f"  → {tool_name} 返回: {json.dumps(result, ensure_ascii=False)[:200]}")
                
                # 记录成功的工具执行
                self.recorder.record(step=state.step, phase="agent", tool=tool_name,
                                    params=params, result=result,
                                    state_before=state_before, llm_reason=reason)
                
                # Update state based on result
                self._update_state(state, tool_name, params, result)
                history.append(f"{tool_name}: {params} → {result.get('status', 'unknown')}")
                state.consecutive_no_progress = 0  # Reset on success
                
                # 每 3 步保存一次 checkpoint
                if state.step % 3 == 0:
                    ckpt_path = self._save_checkpoint(state, history, deterministic_done)
                    print(f"  Checkpoint 已保存: {ckpt_path}")
                
            except Exception as e:
                print(f"  → {tool_name} 失败: {e}")
                state.last_error = str(e)
                state.consecutive_no_progress += 1
                # 记录失败的工具执行
                self.recorder.record(step=state.step, phase="agent", tool=tool_name,
                                    params=params, result={},
                                    state_before=state_before, llm_reason=reason, error=str(e))
                history.append(f"{tool_name}: {params} → 失败: {e}")
                
                # Check for no progress
                if state.consecutive_no_progress >= 5:
                    console.print("[red]连续5步无进展，终止[/]")
                    break

        # 保存 agent 报告
        from ..utils import timestamp
        report_dir = CONFIG.outputs_dir / "mcp_agent"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.recorder.save(report_dir / f"{timestamp()}_agent_report.json")
        print(f"Agent 报告已保存: {report_path}")
        print(self.recorder.summary())

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

    def _save_checkpoint(self, state: AgentState, history: list[str],
                        deterministic_done: list[str]) -> Path:
        """保存当前进度到 checkpoint 文件。"""
        from ..utils import timestamp
        
        data = {
            "version": 1,
            "url": self._url,
            "session_dir": str(CONFIG.session_dir),
            "deterministic_done": deterministic_done,
            "state": {
                "step": state.step,
                "page_url": state.page_url,
                "field_count": state.field_count,
                "filled_fields": state.filled_fields,
                "failed_fields": state.failed_fields,
                "verified_fields": state.verified_fields,
                "last_error": state.last_error,
            },
            "history": history[-50:],   # 保留最近 50 条
        }
        
        checkpoint_dir = CONFIG.outputs_dir / "mcp_agent"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        path = checkpoint_dir / f"checkpoint_{timestamp()}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _load_checkpoint(path: str) -> dict:
        """加载 checkpoint 文件。"""
        from pathlib import Path
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint 不存在: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _parse_tool_call(self, response):
        """Parse tool call from LLM response (handles both dict and str)."""
        if isinstance(response, dict):
            return response.get("tool"), response.get("params", {})
        
        try:
            obj = json.loads(str(response))
            return obj.get("tool"), obj.get("params", {})
        except (json.JSONDecodeError, TypeError):
            return None


def run_agent(url: str, resume_from: str = "") -> None:
    llm = create_llm_client()
    agent = MCPAgent(llm_client=llm, resume_from=resume_from)
    agent.run(url, resume_from=resume_from)
