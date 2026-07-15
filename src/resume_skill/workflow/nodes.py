"""Node implementations for the LangGraph application workflow."""

from __future__ import annotations

import re
from typing import Any, Dict

from .browser_executor import BrowserExecutorNode
from .planner_node import ApplicationPlannerNode
from .recovery_node import GuiRecoveryNode
from .state import ApplicationState
from .verify_node import VerifyResultNode


def _history(state: ApplicationState, entry: dict[str, Any]) -> list[dict[str, Any]]:
    return state.get("execution_history", []) + [entry]


def _workflow_vision_client(state: ApplicationState) -> Any:
    vision = state.get("_vision_client")
    if vision and not hasattr(vision, "verify"):
        try:
            from resume_skill.llm.vision import VisionWorkflowAdapter

            return VisionWorkflowAdapter(vision)
        except Exception:
            return vision
    return vision


def _parse_snapshot_to_form(snapshot: Any) -> dict[str, dict[str, Any]]:
    """Convert Chrome MCP text snapshots into a minimal application_form map."""
    if isinstance(snapshot, dict) and "content" in snapshot:
        parts = []
        for item in snapshot.get("content", []):
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        snapshot = "\n".join(parts)

    if isinstance(snapshot, dict):
        nodes = snapshot.get("nodes", [])
        form: dict[str, dict[str, Any]] = {}
        for node in nodes:
            uid = str(node.get("uid", ""))
            label = str(node.get("label", node.get("name", "")))
            role = str(node.get("role", node.get("type", "text"))).lower()
            if not uid:
                continue
            field_type = "file" if re.search(r"上传|附件|简历|resume|upload|file", label, re.I) else role
            if field_type in {"textbox", "textarea", "searchbox"}:
                field_type = "text"
            if field_type in {"combobox", "listbox"}:
                field_type = "select"
            if field_type in {"text", "select", "checkbox", "radio", "file"}:
                form[uid] = {"uid": uid, "label": label, "type": field_type, "required": True, "value": ""}
        return form

    text = str(snapshot or "")
    form = {}
    role_map = {
        "textbox": "text",
        "textarea": "text",
        "searchbox": "text",
        "combobox": "select",
        "listbox": "select",
        "checkbox": "checkbox",
        "radio": "radio",
        "button": "button",
    }
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = re.match(r'(\w+)\s+"([^"]*)"\s+uid=([\w_]+)', line)
        if match:
            role, label, uid = match.group(1), match.group(2), match.group(3)
        else:
            match = re.match(r'uid=([\w_]+)\s+(\w+)\s+"([^"]*)"', line)
            if not match:
                continue
            uid, role, label = match.group(1), match.group(2), match.group(3)
        field_type = role_map.get(role)
        if role == "button" and re.search(r"上传|附件|简历|resume|upload|file", label, re.I):
            field_type = "file"
        if field_type in {"text", "select", "checkbox", "radio", "file"}:
            form[uid] = {"uid": uid, "label": label, "type": field_type, "required": True, "value": ""}
    return form


def resume_analyzer_node(state: ApplicationState) -> Dict[str, Any]:
    return {
        "resume_data": state.get("resume_data", {}),
        "execution_history": _history(state, {"step": "resume_analyzer", "status": "skipped"}),
    }


def job_description_analyzer_node(state: ApplicationState) -> Dict[str, Any]:
    return {
        "job_description": state.get("job_description", {}),
        "execution_history": _history(state, {"step": "job_description_analyzer", "status": "skipped"}),
    }


def resume_customization_node(state: ApplicationState) -> Dict[str, Any]:
    return {
        "generated_documents": state.get("generated_documents", {}),
        "execution_history": _history(state, {"step": "resume_customization", "status": "skipped"}),
    }


def cover_letter_generator_node(state: ApplicationState) -> Dict[str, Any]:
    generated = dict(state.get("generated_documents", {}))
    generated.setdefault("cover_letter", "")
    return {
        "generated_documents": generated,
        "execution_history": _history(state, {"step": "cover_letter_generator", "status": "skipped"}),
    }


def application_planner_node(state: ApplicationState) -> Dict[str, Any]:
    llm_client = state.get("_llm_client")
    planner = ApplicationPlannerNode(llm_client=llm_client)
    result = planner.plan(state)
    result["current_task"] = result.get("current_task", "browser_execution")
    if llm_client:
        result.setdefault("llm_decision_log", state.get("llm_decision_log", []))
    return result


def browser_executor_node(state: ApplicationState) -> Dict[str, Any]:
    chrome = state.get("_chrome_client")
    executor = BrowserExecutorNode(chrome_client=chrome)
    result = executor.execute(state)

    browser_context = result.get("browser_context", state.get("browser_context", {}))
    snapshot = browser_context.get("snapshot")
    if snapshot and not state.get("application_form"):
        parsed_form = _parse_snapshot_to_form(snapshot)
        if parsed_form:
            result["application_form"] = parsed_form
            result["execution_history"] = result.get("execution_history", state.get("execution_history", [])) + [
                {
                    "step": "browser_executor.parse_snapshot",
                    "status": "completed",
                    "field_count": len(parsed_form),
                    "message": f"Parsed {len(parsed_form)} form fields from snapshot",
                }
            ]
        else:
            result["errors"] = result.get("errors", state.get("errors", [])) + [
                "未识别到可填写表单字段：请确认 Chrome 当前页面停留在网申表单页，而不是首页、登录页或空白页"
            ]

    action = state.get("next_action", {})
    if isinstance(action, dict) and action.get("type") in {"fill", "type_text", "upload_file"}:
        uid = action.get("uid")
        application_form = dict(result.get("application_form", state.get("application_form", {})))
        if uid in application_form and not result.get("gui_recovery_needed"):
            field = dict(application_form[uid])
            if action.get("type") == "upload_file":
                field["value"] = action.get("file_path") or state.get("resume_pdf_path", "")
            else:
                field["value"] = action.get("value", "")
            field["verified"] = True
            application_form[uid] = field
            result["application_form"] = application_form

    result["current_task"] = "verification"
    return result


def verify_result_node(state: ApplicationState) -> Dict[str, Any]:
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 20))
    if retry_count >= max_retries:
        return {
            "manual_required": True,
            "gui_recovery_needed": False,
            "current_task": "end",
            "execution_history": _history(state, {"step": "verify_result", "status": "max_retries"}),
        }

    verifier = VerifyResultNode(vision_client=_workflow_vision_client(state))
    result = verifier.verify(state)
    if result.get("gui_recovery_needed"):
        result["retry_count"] = retry_count + 1
    elif not result.get("success") and not result.get("manual_required"):
        result["retry_count"] = retry_count + 1
        if retry_count + 1 >= max_retries:
            result["manual_required"] = True
            result["current_task"] = "end"
    result.setdefault("current_task", "end" if result.get("success") or result.get("manual_required") else "application_planning")
    return result


def gui_recovery_node(state: ApplicationState) -> Dict[str, Any]:
    recovery = GuiRecoveryNode(
        vision_client=_workflow_vision_client(state),
        chrome_client=state.get("_chrome_client"),
    )
    result = recovery.recover(state)
    result.setdefault("current_task", "application_planning")
    return result
