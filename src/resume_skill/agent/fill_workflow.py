"""
LangGraph-based workflow for form filling with background task support.
Replaces synchronous fill with state-managed async workflow.
"""

from __future__ import annotations

import json
import time
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from pathlib import Path

from ..config import CONFIG


@dataclass
class ApplicationState:
    """State managed by LangGraph workflow for fill operations."""
    task_id: str
    user_profile: dict[str, Any] = field(default_factory=dict)
    resume_pdf_path: str = ""
    max_retries: int = 20
    current_task: str = "初始化填写任务"
    
    # Resume analysis (populated by ResumeAnalyzerNode)
    resume_data: dict[str, Any] = field(default_factory=dict)
    unified_profile: dict[str, Any] = field(default_factory=dict)
    
    # Workflow progress
    status: str = "pending"  # pending, running, completed, failed, cancelled
    step: int = 0
    log: list[str] = field(default_factory=list)
    
    # Form analysis
    fields: list[dict[str, Any]] = field(default_factory=list)
    fill_plan: list[dict[str, Any]] = field(default_factory=list)
    
    # Execution results
    filled_count: int = 0
    failed_count: int = 0
    manual_required: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    
    # Vision review
    vision_review: dict[str, Any] = field(default_factory=dict)
    vision_ok: bool = False
    success: bool = False
    
    def add_log(self, msg: str):
        """Add timestamped log entry."""
        timestamp = time.strftime("%H:%M:%S")
        self.log.append(f"[{timestamp}] {msg}")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class FillWorkflowRunner:
    """Runner for LangGraph-based fill workflow."""
    
    def __init__(self, chrome_client: Any, llm_client: Any, vision_client: Optional[Any] = None):
        self.chrome = chrome_client
        self.llm = llm_client
        self.vision = vision_client
    
    def run(self, state: ApplicationState) -> ApplicationState:
        """Execute fill workflow with state updates."""
        state.status = "running"
        state.add_log("工作流启动")
        
        try:
            # Step 1: Observe current page
            state = self._step_observe(state)
            if state.status == "failed":
                return state
            
            # Step 2: Plan filling strategy
            state = self._step_plan(state)
            if state.status == "failed":
                return state
            
            # Step 3: Execute filling
            state = self._step_execute(state)
            if state.status == "failed":
                return state
            
            # Step 4: Vision verification
            state = self._step_verify(state)
            
            # Step 5: Determine success
            state.success = state.vision_ok and state.failed_count == 0
            state.status = "completed"
            state.current_task = "任务完成"
            state.add_log(f"工作流完成，成功: {state.success}")
            
        except Exception as e:
            state.status = "failed"
            state.errors.append(str(e))
            state.add_log(f"工作流异常: {e}")
        
        return state
    
    def _step_observe(self, state: ApplicationState) -> ApplicationState:
        """Step 1: Observe current page and extract form."""
        state.current_task = "正在观察页面..."
        state.add_log("Step 1: 观察页面")
        state.step = 1
        
        try:
            # Take snapshot
            snapshot = self.chrome.call_tool("take_snapshot", {}, timeout=15)
            if not snapshot or not str(snapshot).strip():
                state.status = "failed"
                state.errors.append("页面无障碍树为空")
                state.add_log("页面读取失败")
                return state
            
            snapshot_text = str(snapshot)
            state.add_log(f"页面读取成功，{len(snapshot_text)} 字符")
            
            # Parse form fields using existing extractors
            try:
                from resume_skill.agent.form_extractor import extract_form_fields
                fields = extract_form_fields(self.chrome, state.user_profile, self.llm) if self.llm else []
            except Exception:
                fields = []
            
            if not fields:
                state.add_log("警告: 未检测到表单字段，尝试规则提取")
                try:
                    from resume_skill.agent.form_extractor import extract_fields_rule_based
                    fields = extract_fields_rule_based(self.chrome)
                except Exception:
                    fields = []
            
            state.fields = fields
            state.add_log(f"检测到 {len(fields)} 个表单字段")
            
        except Exception as e:
            state.status = "failed"
            state.errors.append(f"观察失败: {e}")
            state.add_log(f"观察失败: {e}")
        
        return state
    
    def _step_plan(self, state: ApplicationState) -> ApplicationState:
        """Step 2: Plan filling strategy using LLM."""
        state.current_task = "正在规划填写策略..."
        state.add_log("Step 2: 规划填写策略")
        state.step = 2
        
        try:
            if not self.llm:
                state.add_log("警告: 无 LLM 客户端，使用规则匹配")
                from resume_skill.agent.field_matcher import match_fields_rule_based
                fill_plan = match_fields_rule_based(state.fields, state.user_profile)
            else:
                from resume_skill.agent.field_matcher import match_fields_with_llm
                fill_plan = match_fields_with_llm(
                    state.fields,
                    state.user_profile,
                    self.llm,
                    jd_analysis={}
                )
            
            state.fill_plan = fill_plan
            state.add_log(f"规划完成: {len(fill_plan)} 个字段")
            
            # Categorize by action
            auto_fill = [p for p in fill_plan if p.get("action") == "fill" and p.get("confidence", 0) > 0.6]
            manual = [p for p in fill_plan if p.get("action") == "manual"]
            state.manual_required = manual
            state.add_log(f"自动填充: {len(auto_fill)}, 手动: {len(manual)}")
            
        except Exception as e:
            state.status = "failed"
            state.errors.append(f"规划失败: {e}")
            state.add_log(f"规划失败: {e}")
        
        return state
    
    def _step_execute(self, state: ApplicationState) -> ApplicationState:
        """Step 3: Execute form filling."""
        state.current_task = "正在执行填充..."
        state.add_log("Step 3: 执行填充")
        state.step = 3
        
        try:
            from resume_skill.agent.form_filler import fill_form
            
            auto_fill = [p for p in state.fill_plan if p.get("action") == "fill" and p.get("confidence", 0) > 0.6]
            if not auto_fill:
                state.add_log("无可自动填充的字段")
                return state
            
            # Execute filling
            result = fill_form(
                self.chrome,
                state.fill_plan,
                resume_path=state.resume_pdf_path if state.resume_pdf_path else None
            )
            
            state.filled_count = len(result.get("filled", []))
            state.failed_count = len(result.get("failed", []))
            state.add_log(f"填充完成: 成功 {state.filled_count}, 失败 {state.failed_count}")
            
        except Exception as e:
            state.errors.append(f"执行失败: {e}")
            state.add_log(f"执行失败: {e}")
        
        return state
    
    def _step_verify(self, state: ApplicationState) -> ApplicationState:
        """Step 4: Vision verification of filled form."""
        state.current_task = "正在验证填充结果..."
        state.add_log("Step 4: 视觉验证")
        state.step = 4
        
        try:
            if not self.vision:
                state.add_log("无视觉客户端，跳过视觉验证")
                state.vision_ok = state.failed_count == 0
                return state
            
            # Take screenshot and verify
            screenshot = self.chrome.call_tool("take_screenshot", {}, timeout=20)
            if not screenshot:
                state.add_log("截图失败")
                state.vision_ok = False
                return state
            
            from ..webui.app import _screenshot_to_bytes, _vision_review_fill
            image_bytes = _screenshot_to_bytes(screenshot)
            
            snapshot = self.chrome.call_tool("take_snapshot", {}, timeout=15)
            snapshot_text = str(snapshot) if snapshot else ""
            
            vision_result = _vision_review_fill(self.chrome, state.fields, snapshot_text)
            state.vision_review = vision_result
            state.vision_ok = bool(vision_result.get("ok", False))
            state.add_log(f"视觉验证完成: {'通过' if state.vision_ok else '未通过'}")
            
        except Exception as e:
            state.errors.append(f"视觉验证失败: {e}")
            state.add_log(f"视觉验证失败: {e}")
            state.vision_ok = False
        
        return state


def load_user_profile(profile_path: Optional[str] = None) -> dict[str, Any]:
    """Load user profile from markdown or YAML."""
    if profile_path:
        p = Path(profile_path)
        if p.exists():
            if p.suffix == ".md":
                return {"raw_md": p.read_text(encoding="utf-8")}
            elif p.suffix in [".yaml", ".yml"]:
                from ..agent.utils import load_yaml
                return load_yaml(p) or {}
    
    # Try default location
    default_path = CONFIG.personal_info_dir / "profile_template.md"
    if default_path.exists():
        return {"raw_md": default_path.read_text(encoding="utf-8")}
    
    return {}
