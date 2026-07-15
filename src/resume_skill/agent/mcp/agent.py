"""
LLM Agent v2.4: dual MCP server (ours + Google Chrome DevTools).

Flow: take_snapshot → parse fields → LLM Q&A → fill loop.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ...llm.factory import create_llm_client
from ...llm.base import BaseLLMClient
from ...config import CONFIG
from .client import MCPClient
from .chrome_client import ChromeDevToolsClient
from .recorder import AgentRecorder
from ..utils import load_yaml, print_section, console


@dataclass
class AgentState:
    step: int = 0
    page_url: str = ""
    field_count: int = 0
    filled_fields: list[dict] = field(default_factory=list)
    failed_fields: list[dict] = field(default_factory=list)
    max_steps: int = 10

    def to_prompt(self) -> str:
        return json.dumps(
            {
                "当前步骤": self.step,
                "已填充字段": [f.get("uid", "") for f in self.filled_fields],
                "失败字段": [f.get("uid", "") for f in self.failed_fields],
            },
            ensure_ascii=False,
        )


class MCPAgent:
    """Dual MCP Server Agent: Google Chrome DevTools + our own tools."""

    def __init__(self, llm_client: BaseLLMClient | None = None, resume_from: str = "", headless: bool = False):
        self.chrome = ChromeDevToolsClient(headless=headless)
        use_sdk = bool(CONFIG.mcp.python_path)
        self.our_client = MCPClient(
            use_mcp_sdk=use_sdk,
            mcp_python_path=CONFIG.mcp.python_path,
        )
        self.llm = llm_client or create_llm_client()
        self.profile: dict[str, Any] = {}
        self.recorder = AgentRecorder()
        self._resume_from = resume_from

    def _load_profile(self) -> str:
        """Load profile_template.md as the source of truth. Fallback to unified_profile.yaml."""
        md_path = CONFIG.personal_info_dir / "profile_template.md"
        if md_path.exists():
            return md_path.read_text(encoding="utf-8")
        yaml_path = CONFIG.unified_profile_path
        if yaml_path.exists():
            data = load_yaml(yaml_path) or {}
            return json.dumps(data, ensure_ascii=False, indent=2)
        print(f"[WARNING] No profile found at {md_path} or {yaml_path}")
        return ""

    # ─── snapshot 解析 ──────────────────────────────────

    def _parse_snapshot(self, snapshot_text: str) -> list[dict]:
        """
        解析 chrome-devtools-mcp 的 take_snapshot 返回的无障碍树文本，提取表单字段列表。

        take_snapshot 返回的文本格式示例:
            textbox "姓名" uid=1_5
            textbox "邮箱" uid=1_6  
            combobox "学历" uid=1_7 options="本科,硕士,博士"
            button "提交" uid=1_8

        返回: [{uid, label, type, options}, ...]
        """
        form_roles = {"textbox", "combobox", "textarea", "searchbox", "listbox", "checkbox", "radio", "button"}
        type_map = {
            "combobox": "select",
            "listbox": "select",
            "textbox": "text",
            "textarea": "text",
            "searchbox": "text",
            "checkbox": "checkbox",
            "radio": "radio",
            "button": "button",
        }

        fields = []
        for line in snapshot_text.split("\n"):
            line = line.strip()
            # 支持旧格式 `textbox "姓名" uid=1_5` 和新版 `uid=1_5 textbox "姓名"`。
            m = re.match(r'(\w+)\s+"([^"]*)"\s+uid=([\w_]+)', line)
            if not m:
                m = re.match(r'uid=([\w_]+)\s+(\w+)\s+"([^"]*)"', line)
                if m:
                    uid, role, label = m.group(1), m.group(2), m.group(3)
                else:
                    continue
            else:
                role, label, uid = m.group(1), m.group(2), m.group(3)

            if role not in form_roles:
                continue

            field_type = type_map.get(role, "text")
            if role == "button" and not re.search(r"上传|附件|简历|resume|upload|file", label, re.I):
                continue
            if role == "button":
                field_type = "file"

            # 提取 options（combobox 可能有 options="a,b,c"）
            options = []
            om = re.search(r'options="([^"]*)"', line)
            if om:
                options = [o.strip() for o in om.group(1).split(",") if o.strip()]

            fields.append(
                {
                    "uid": uid,
                    "label": label,
                    "type": field_type,
                    "options": options,
                }
            )

        return fields

    def _find_submit_uid(self, snapshot_text: str) -> str:
        """在无障碍树中找到提交按钮的 uid。"""
        keywords = ["提交", "投递", "Submit", "submit", "Apply", "apply"]
        for line in snapshot_text.split("\n"):
            line_lower = line.lower()
            for kw in keywords:
                if kw.lower() in line_lower:
                    m = re.search(r"uid=([\w_]+)", line)
                    if m:
                        return m.group(1)
        return ""

    # ─── LLM Q&A 匹配 ──────────────────────────────────

    def _answer_fields(self, fields: list[dict]) -> list[dict]:
        """
        将表单字段列表 + 用户档案（MD格式）打包成一个 LLM 调用，LLM 以 Q&A 方式回答每个字段应填什么。

        返回: [{uid, answer, confidence, action}, ...]
        """
        fields_json = json.dumps(fields, ensure_ascii=False, indent=2)

        prompt = f"""你是一个严谨的网申表单填写助手。你的任务是根据用户档案（MD格式）一次性地为所有表单字段给出答案。

## 核心要求

1. **推理能力** — 不要只找精确匹配，要从已有信息中推理：
   - 如果档案中有出生日期但没有年龄 → 推算年龄（用2026年）
   - 如果档案中有学校的"计算机科学与技术"专业，字段是"就读院系" → 填"计算机科学与技术"
   - 如果档案中有毕业时间 → 可以推算"是否应届"
   - 如果档案中有 GitHub 链接 → 可以推断"是否会 Git"
   - 下拉选项：从 options 中选最接近的，不要空着

2. **一次性回答所有字段** — 所有字段一次性给出答案，不要分批

3. **严谨负责** — 有根据地填写，不随意编造。确实不知道的 confidence 填 "low"，不是在瞎猜的填 "high"

## 分类标准

- **confidence = high**: 档案中有确切对应信息（如姓名、邮箱、学校等），答案确定
- **confidence = medium**: 通过推理得到的信息（如从出生日期推算年龄、从专业推断技能等），较确定
- **confidence = low**: 没有任何信息线索，只能用常识推测或完全不知道

- **action = fill**: 正常字段，自动填入
- **action = manual**: 敏感字段（身份证号、政治面貌、银行卡号、家庭住址、护照号等），需要用户自己填

## 用户档案
{self.profile}

## 表单字段（一次性全部回答）
{fields_json}

返回纯 JSON（不要 markdown 代码块），格式：
{{"answers": [{{"uid": "...", "answer": "...", "confidence": "high/medium/low", "action": "fill/manual"}}]}}"""
        result = self.llm.call_json("", prompt)
        if isinstance(result, dict) and "answers" in result:
            return result["answers"]
        return []

    # ─── 主流程 ─────────────────────────────────────────

    def run(self, url: str, resume_from: str = "") -> None:
        print_section("MCP Agent v2.4 - 智能填充流程")

        self.profile = self._load_profile()
        if not self.profile:
            console.print("[red]找不到用户档案（profile_template.md），请先在 WebUI 中上传简历并提取[/]")
            return

        # 连接双 MCP Server
        self.chrome.connect()
        self.our_client.connect()

        state = AgentState()

        # ===== Step 1: 打开页面 =====
        print("[Step 1] 打开招聘页面...")
        self.chrome.call_tool("navigate_page", {"url": url})
        self.recorder.record(
            step=1,
            phase="deterministic",
            tool="navigate_page",
            params={"url": url},
            result={"status": "navigated"},
            state_before="",
            llm_reason="",
        )

        # ===== Step 2: 等用户登录 =====
        print("[Step 2] 等待用户手动登录...")
        self.our_client.call_tool(
            "wait_for_user",
            {"message": "请在浏览器中完成登录后按 Enter 继续..."},
        )
        self.recorder.record(
            step=2,
            phase="deterministic",
            tool="wait_for_user",
            params={},
            result={"status": "continue"},
            state_before="",
            llm_reason="",
        )

        # ===== Step 3-N: 多页循环 =====
        while state.step < state.max_steps:
            state.step += 1
            print(f"\n{'='*50}")
            print(f"Round {state.step}")
            print(f"{'='*50}")

            # 3a. 获取无障碍树
            try:
                snapshot = self.chrome.call_tool("take_snapshot", {})
                snapshot_str = str(snapshot)
            except Exception as e:
                print(f"[错误] take_snapshot 失败: {e}")
                break

            # 3b. 解析字段
            fields = self._parse_snapshot(snapshot_str)
            state.field_count = len(fields)
            print(f"[解析] 检测到 {len(fields)} 个表单字段")

            if not fields:
                print("[判断] 当前页面没有表单字段，可能已是最后一页")
                submit_uid = self._find_submit_uid(snapshot_str)
                if submit_uid:
                    print(f"[提交] 点击提交按钮 uid={submit_uid}")
                    try:
                        self.chrome.call_tool("click", {"uid": submit_uid})
                        self.recorder.record(
                            step=state.step,
                            phase="agent",
                            tool="click",
                            params={"uid": submit_uid},
                            result={"status": "clicked"},
                            state_before=state.to_prompt(),
                            llm_reason="点击提交按钮",
                        )
                    except Exception as e:
                        print(f"[错误] 提交失败: {e}")
                    break

            # 3c. LLM Q&A 获取答案
            print("[LLM] 分析字段并匹配用户档案...")
            try:
                answers = self._answer_fields(fields)
                print(f"[LLM] 返回 {len(answers)} 个答案")
            except Exception as e:
                print(f"[错误] LLM 问答失败: {e}")
                break

            # 3d. 逐字段填充
            any_filled = False
            for ans in answers:
                uid = ans.get("uid", "")
                action = ans.get("action", "fill")
                answer = ans.get("answer", "")
                confidence = ans.get("confidence", "low")

                if action == "manual":
                    state.failed_fields.append(
                        {
                            "uid": uid,
                            "reason": f"敏感字段 ({answer})",
                        }
                    )
                    print(f"  ⚠️ {uid}: 敏感字段，跳过 ({answer})")
                    continue

                if not answer or answer == "未提供":
                    print(f"  ⊘ {uid}: 未找到匹配数据，跳过")
                    continue

                if confidence == "low":
                    print(f"  ⚠️ {uid}: 低置信度 ({answer[:30]})，跳过")
                    continue

                try:
                    print(f"  → fill uid={uid} = {answer[:40]} [{confidence}]")
                    self.chrome.call_tool("fill", {"uid": uid, "value": answer})
                    any_filled = True
                    state.filled_fields.append({"uid": uid, "answer": answer})
                    self.recorder.record(
                        step=state.step,
                        phase="agent",
                        tool="fill",
                        params={"uid": uid, "value": answer},
                        result={"status": "filled"},
                        state_before=state.to_prompt(),
                        llm_reason=confidence,
                    )
                except Exception as e:
                    print(f"  ❌ {uid} 填充失败: {e}")
                    state.failed_fields.append({"uid": uid, "error": str(e)})
                    self.recorder.record(
                        step=state.step,
                        phase="agent",
                        tool="fill",
                        params={"uid": uid, "value": answer},
                        result={"status": "failed"},
                        state_before=state.to_prompt(),
                        llm_reason=confidence,
                        error=str(e),
                    )

            if not any_filled:
                print("[警告] 本轮没有成功填充任何字段，可能所有字段都未匹配或置信度低")
                break

            # 3e. 尝试点击"下一步"按钮（翻页）
            next_uid = self._find_next_uid(snapshot_str)
            if next_uid:
                print(f"[翻页] 点击下一步按钮 uid={next_uid}")
                try:
                    self.chrome.call_tool("click", {"uid": next_uid})
                except Exception as e:
                    print(f"[翻页] 失败: {e}")
                    break
            else:
                print("[判断] 没有检测到下一步按钮，当前页可能已是最后一页")
                # 尝试提交
                submit_uid = self._find_submit_uid(snapshot_str)
                if submit_uid:
                    print(f"[提交] 点击提交按钮 uid={submit_uid}")
                    self.chrome.call_tool("click", {"uid": submit_uid})
                    break

        # ===== 结束 =====
        report_dir = CONFIG.outputs_dir / "mcp_agent"
        report_dir.mkdir(parents=True, exist_ok=True)
        from ..utils import timestamp

        report_path = self.recorder.save(report_dir / f"{timestamp()}_agent_report.json")
        print(f"\n[报告] 已保存: {report_path}")
        print(self.recorder.summary())

        self.chrome.close()
        self.our_client.close()
        console.print("[green]流程完成[/]")

    def _find_next_uid(self, snapshot_text: str) -> str:
        """在无障碍树中找到'下一步'或'下一页'按钮的 uid。"""
        keywords = ["下一步", "下一页", "继续", "Next", "next", "Continue"]
        for line in snapshot_text.split("\n"):
            line_lower = line.lower()
            for kw in keywords:
                if kw.lower() in line_lower:
                    m = re.search(r"uid=([\w_]+)", line)
                    if m:
                        return m.group(1)
        return ""


def run_agent(url: str, resume_from: str = "", headless: bool = False) -> None:
    llm = create_llm_client()
    agent = MCPAgent(llm_client=llm, resume_from=resume_from, headless=headless)
    agent.run(url, resume_from=resume_from)
