"""
ApplicationPlannerNode: 使用文本模型逐步规划单个动作的节点。

流程：
  1. 输入 state（包含 user_profile, application_form, snapshot, execution_history, resume_pdf_path）
  2. 调用 LLM 规划一次只填一个字段的动作
  3. 输出 state.next_action
  4. JSON 解析失败时，返回 manual action 并设置错误原因
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ...llm.factory import create_llm_client
from ...llm.base import BaseLLMClient
from ...config import CONFIG
from ..utils import console


@dataclass
class ApplicationState:
    """应用表单填充的状态"""
    # 输入
    user_profile: dict[str, Any] = field(default_factory=dict)  # 用户档案
    application_form: list[dict] = field(default_factory=list)  # 表单字段列表
    browser_context_snapshot: str = ""  # 页面快照
    execution_history: list[dict] = field(default_factory=list)  # 已执行的动作历史
    resume_pdf_path: str = ""  # 简历 PDF 路径
    
    # 输出
    next_action: dict[str, Any] = field(default_factory=dict)  # 下一步动作
    
    # 元数据
    current_field_uid: str = ""  # 当前处理的字段 uid
    page_url: str = ""  # 当前页面 URL
    page_index: int = 0  # 当前页面序号
    
    def to_history_str(self) -> str:
        """将执行历史转为字符串表示"""
        if not self.execution_history:
            return "无"
        lines = []
        for i, action in enumerate(self.execution_history[-10:], 1):  # 最多显示最后 10 条
            uid = action.get("uid", "")
            action_type = action.get("type", "")
            value = action.get("value", "")[:30]
            lines.append(f"{i}. {action_type} uid={uid} value={value}")
        return "\n".join(lines)


class ApplicationPlannerNode:
    """使用 LLM 决策的单步动作规划节点"""

    def __init__(self, llm_client: BaseLLMClient | None = None):
        self.llm = llm_client or create_llm_client()

    def _build_field_context(self, field: dict) -> str:
        """为当前字段构建上下文信息"""
        uid = field.get("uid", "")
        label = field.get("label", "")
        field_type = field.get("type", "")
        options = field.get("options", [])
        
        context = f"uid={uid} | label={label} | type={field_type}"
        if options:
            context += f" | options={','.join(options[:5])}"
        return context

    def _find_next_field(self, state: ApplicationState) -> dict | None:
        """找到下一个未填充的字段"""
        filled_uids = {a.get("uid") for a in state.execution_history if a.get("type") == "fill"}
        
        for field in state.application_form:
            uid = field.get("uid", "")
            field_type = field.get("type", "")
            
            # 跳过已填充的字段
            if uid in filled_uids:
                continue
            
            # 跳过按钮类型（这些由 click 和 done 处理）
            if field_type == "button":
                continue
            
            return field
        
        return None

    def _is_sensitive_field(self, label: str) -> bool:
        """判断是否为敏感字段"""
        sensitive_keywords = [
            "身份证",
            "政治面貌",
            "家庭住址",
            "护照号",
            "银行卡",
            "社会信用代码",
            "组织机构代码",
            "税务登记号",
            "隐私",
            "个人信息",
        ]
        label_lower = label.lower()
        return any(kw.lower() in label_lower for kw in sensitive_keywords)

    def _is_file_field(self, field: dict) -> bool:
        """判断是否为文件上传字段"""
        label = field.get("label", "").lower()
        field_type = field.get("type", "").lower()
        
        file_keywords = ["上传", "附件", "简历", "resume", "upload", "file", "document", "证件", "照片"]
        return any(kw.lower() in label for kw in file_keywords) or field_type == "file"

    def _is_dropdown_field(self, field: dict) -> bool:
        """判断是否为下拉/选择字段"""
        return field.get("type") in {"select", "combobox", "dropdown", "radio", "checkbox"}

    def _create_manual_action(self, reason: str) -> dict:
        """创建手动操作 action"""
        return {
            "type": "manual",
            "reason": reason,
        }

    def _create_observe_action(self, reason: str = "无法确定字段信息") -> dict:
        """创建观察 action"""
        return {
            "type": "observe",
            "reason": reason,
        }

    def _call_llm_planner(self, state: ApplicationState, field: dict) -> dict[str, Any]:
        """
        调用 LLM 规划单个字段的填充动作。
        
        返回格式必须是 JSON：
        {
            "type": "fill|fill_form|click|upload_file|manual|observe|done",
            "uid": "field_uid",
            "value": "填充值（仅对 fill/fill_form）",
            "target": "字段名（用户友好名称）",
            "reason": "为什么选择这个动作"
        }
        """
        field_context = self._build_field_context(field)
        
        # 构建档案信息摘要
        profile_summary = self._summarize_profile(state.user_profile)
        
        # 构建历史摘要
        history_summary = state.to_history_str()
        
        prompt = f"""你是一个严谨的网申表单填充规划器。你需要为以下字段规划一个填充动作。

## 核心要求

1. **一次只规划一个动作** — 不要一次填多个字段
2. **视觉确认完成** — 当所有字段都已完成时，返回 {{"type": "done"}}
3. **字段分类策略**：
   - 普通文本框（text）：fill
   - 多个稳定的同类字段（e.g., 多个文本框）：可以 fill_form
   - 下拉/自定义控件（select/combobox）：优先 click 展开，不要直接乱填
   - 文件/附件/简历上传：upload_file
   - 敏感字段（身份证、政治面貌等）：manual
   - 无法确定的字段：observe
4. **置信度原则** — 只填有把握的值；不确定的用 observe 或 manual
5. **返回纯 JSON**（不要 markdown 代码块）

## 用户档案摘要
{profile_summary}

## 当前表单字段
{field_context}

## 执行历史（最近 10 条）
{history_summary}

## 页面快照摘要
{state.browser_context_snapshot[:500]}

根据上述信息，为当前字段规划一个动作。返回 JSON：
{{"type": "...", "uid": "...", "value": "...", "target": "...", "reason": "..."}}
"""
        
        try:
            result = self.llm.call_json("", prompt)
            return result
        except Exception as e:
            # JSON 解析失败
            console.print(f"[red]LLM JSON 解析失败: {e}[/]")
            return {}

    def _summarize_profile(self, profile: dict) -> str:
        """将用户档案转为简洁的摘要"""
        if not profile:
            return "无用户档案"
        
        summary_lines = []
        
        # 基础信息
        if "personal" in profile:
            personal = profile["personal"]
            if personal.get("name_cn"):
                summary_lines.append(f"姓名: {personal['name_cn']}")
            if personal.get("email"):
                summary_lines.append(f"邮箱: {personal['email']}")
            if personal.get("phone"):
                summary_lines.append(f"电话: {personal['phone']}")
        
        # 教育背景
        if "education" in profile and profile["education"]:
            edu = profile["education"][0]
            school = edu.get("school", "")
            degree = edu.get("degree", "")
            major = edu.get("major", "")
            summary_lines.append(f"教育: {degree} {major} from {school}")
        
        # 工作经验
        if "experience" in profile and profile["experience"]:
            exp = profile["experience"][0]
            company = exp.get("company", "")
            position = exp.get("position", "")
            summary_lines.append(f"工作: {position} at {company}")
        
        return "\n".join(summary_lines) if summary_lines else "无详细档案"

    def plan(self, state: ApplicationState) -> ApplicationState:
        """
        规划下一步动作。
        
        参数:
            state: 应用状态
        
        返回:
            更新后的 state，包含 next_action
        """
        # 1. 找到下一个未填充的字段
        next_field = self._find_next_field(state)
        
        if not next_field:
            # 所有字段都已处理
            state.next_action = {"type": "done", "reason": "所有字段视觉确认完成"}
            return state
        
        state.current_field_uid = next_field.get("uid", "")
        uid = next_field.get("uid", "")
        label = next_field.get("label", "")
        
        # 2. 预检查：敏感字段 → manual
        if self._is_sensitive_field(label):
            state.next_action = self._create_manual_action(f"敏感字段: {label}")
            return state
        
        # 3. 预检查：文件字段 → upload_file
        if self._is_file_field(next_field):
            state.next_action = {
                "type": "upload_file",
                "uid": uid,
                "target": label,
                "reason": f"检测到文件上传字段: {label}",
            }
            return state
        
        # 4. 预检查：下拉字段 → click（优先展开，不直接填）
        if self._is_dropdown_field(next_field):
            state.next_action = {
                "type": "click",
                "uid": uid,
                "target": label,
                "reason": f"下拉选择字段，优先展开: {label}",
            }
            return state
        
        # 5. 调用 LLM 规划动作
        console.print(f"[cyan]规划字段: {label} (uid={uid})[/]")
        llm_action = self._call_llm_planner(state, next_field)
        
        # 6. 处理 LLM 返回结果
        if not llm_action or not isinstance(llm_action, dict):
            # JSON 解析失败
            state.next_action = self._create_manual_action("planner JSON 解析失败")
            return state
        
        # 验证必要字段
        action_type = llm_action.get("type", "")
        if not action_type:
            state.next_action = self._create_manual_action("LLM 未返回有效的 action type")
            return state
        
        # 允许的 action 类型
        allowed_types = {"fill", "fill_form", "click", "upload_file", "manual", "observe", "done"}
        if action_type not in allowed_types:
            state.next_action = self._create_manual_action(f"非法的 action type: {action_type}")
            return state
        
        # 对于 fill 和 fill_form，需要有 value
        if action_type in {"fill", "fill_form"} and not llm_action.get("value"):
            state.next_action = self._create_observe_action(f"LLM 未返回填充值: {label}")
            return state
        
        # 7. 添加缺失的字段
        if "uid" not in llm_action:
            llm_action["uid"] = uid
        if "target" not in llm_action:
            llm_action["target"] = label
        
        state.next_action = llm_action
        return state


def plan_application(
    user_profile: dict,
    application_form: list[dict],
    browser_snapshot: str = "",
    execution_history: list[dict] | None = None,
    resume_pdf_path: str = "",
    llm_client: BaseLLMClient | None = None,
) -> dict[str, Any]:
    """
    便利函数：快速规划应用表单的下一步动作。
    
    参数:
        user_profile: 用户档案字典
        application_form: 表单字段列表
        browser_snapshot: 页面快照文本
        execution_history: 执行历史
        resume_pdf_path: 简历 PDF 路径
        llm_client: LLM 客户端
    
    返回:
        next_action 字典
    """
    state = ApplicationState(
        user_profile=user_profile,
        application_form=application_form,
        browser_context_snapshot=browser_snapshot,
        execution_history=execution_history or [],
        resume_pdf_path=resume_pdf_path,
    )
    
    planner = ApplicationPlannerNode(llm_client=llm_client)
    updated_state = planner.plan(state)
    return updated_state.next_action
