"""Application Planner Node for deciding next actions."""

import json
from typing import Dict, Any, Optional, List
from .state import ApplicationState


class ApplicationPlannerNode:
    """Plan next application actions based on current state."""
    
    def __init__(self, llm_client=None):
        """Initialize with optional LLM client for planning."""
        self.llm_client = llm_client
    
    def plan(self, state: ApplicationState) -> Dict[str, Any]:
        """Plan the next action."""
        # Check if workflow should end
        if state.get("success") or state.get("manual_required"):
            return self._handle_end_states(state)
        
        # Get current context
        execution_history = state.get("execution_history", [])
        browser_context = state.get("browser_context", {})
        application_form = state.get("application_form", {})
        errors = state.get("errors", [])
        
        # Determine next action
        if self.llm_client:
            return self._plan_with_llm(state)
        else:
            return self._plan_heuristic(state)
    
    def _handle_end_states(self, state: ApplicationState) -> Dict[str, Any]:
        """Handle terminal states."""
        if state.get("success"):
            return {
                "current_task": "end",
                "next_action": {"type": "done"},
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "application_planner",
                        "status": "end",
                        "reason": "Application successful"
                    }
                ]
            }
        else:
            return {
                "current_task": "end",
                "next_action": {"type": "manual"},
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "application_planner",
                        "status": "end",
                        "reason": "Manual intervention required"
                    }
                ]
            }
    
    def _plan_with_llm(self, state: ApplicationState) -> Dict[str, Any]:
        """Plan using LLM model."""
        try:
            # Build planning prompt
            prompt = self._build_planning_prompt(state)
            
            # Call LLM. Providers in this project expose call_text(), while tests may
            # inject a planner object with plan(). Support both.
            if hasattr(self.llm_client, "plan"):
                response = self.llm_client.plan(
                    snapshot=state.get("browser_context", {}).get("snapshot"),
                    application_form=state.get("application_form", {}),
                    execution_history=state.get("execution_history", []),
                    prompt=prompt,
                )
            else:
                response = self.llm_client.call_text("", prompt)
            
            # Parse LLM response
            actions = self._parse_plan_response(response)
            
            if not actions:
                return self._plan_heuristic(state)
            
            # Return first action
            next_action = actions[0]
            if not self._is_valid_planned_action(state, next_action):
                return self._plan_heuristic(state)
            
            return {
                "next_action": next_action,
                "current_task": "browser_execution",
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "application_planner",
                        "status": "planned",
                        "method": "llm",
                        "next_action_type": next_action.get("type")
                    }
                ]
            }
        
        except Exception as e:
            print(f"[ApplicationPlannerNode] LLM planning failed: {e}, using heuristic")
            return self._plan_heuristic(state)

    def _is_valid_planned_action(self, state: ApplicationState, action: Dict[str, Any]) -> bool:
        action_type = action.get("type")
        valid_types = {"observe", "fill", "click", "upload_file", "wait", "done", "manual", "type_text", "press_key"}
        if action_type not in valid_types:
            return False

        uid = action.get("uid")
        form = state.get("application_form", {})
        if action_type in {"fill", "type_text"}:
            if not uid or not action.get("value"):
                return False
            if form.get(uid, {}).get("value"):
                return False
        elif action_type in {"click", "upload_file"}:
            if not uid:
                return False
        elif action_type == "wait":
            value = action.get("value", 1)
            if value in ("", None):
                return False
            try:
                return 0 <= float(value) <= 10
            except (TypeError, ValueError):
                return False
        elif action_type == "done":
            browser_context = state.get("browser_context", {})
            if not browser_context.get("snapshot"):
                return False
            if not form:
                return False
            if any(field.get("required") and not field.get("value") for field in form.values()):
                return False
            history = state.get("execution_history", [])
            has_write_action = any(
                item.get("step") in {"browser_executor.fill", "browser_executor.upload_file", "browser_executor.type_text"}
                and item.get("status") == "completed"
                for item in history
            )
            if not has_write_action:
                return False
        return True
    
    def _plan_heuristic(self, state: ApplicationState) -> Dict[str, Any]:
        """Plan using heuristic rules."""
        snapshot = state.get("browser_context", {}).get("snapshot", {})
        application_form = state.get("application_form", {})
        execution_history = state.get("execution_history", [])
        
        # Find next unfilled field
        nodes = snapshot.get("nodes", []) if isinstance(snapshot, dict) else []
        
        # Strategy 1: Fill unfilled required fields
        for uid, field in application_form.items():
            if field.get("required") and not field.get("value"):
                field = {**field, "uid": uid}
                if not self._field_has_actionable_value(state, field):
                    continue
                return self._plan_fill_field(state, uid, field)
        
        # Strategy 2: Fill any unfilled fields
        for uid, field in application_form.items():
            if not field.get("value"):
                field = {**field, "uid": uid}
                if not self._field_has_actionable_value(state, field):
                    continue
                return self._plan_fill_field(state, uid, field)
        
        # Strategy 3: Observe page state
        if not snapshot:
            return {
                "next_action": {"type": "observe"},
                "current_task": "browser_execution",
                "execution_history": execution_history + [
                    {
                        "step": "application_planner",
                        "status": "planned",
                        "method": "heuristic",
                        "reason": "observe_state"
                    }
                ]
            }
        
        # Strategy 4: Check for upload fields
        upload_field = self._find_upload_field(application_form, nodes)
        if upload_field:
            return self._plan_upload_file(state, upload_field)
        
        # Strategy 5: All known fields filled, mark done. An empty form is not success.
        if application_form and self._all_required_fields_filled(application_form):
            return {
                "next_action": {"type": "done"},
                "current_task": "verification",
                "success": True,
                "execution_history": execution_history + [
                    {
                        "step": "application_planner",
                        "status": "planned",
                        "method": "heuristic",
                        "reason": "all_fields_filled"
                    }
                ]
            }
        
        # Fallback: if required fields remain but no value can be inferred, stop for manual input.
        unfilled = [uid for uid, field in application_form.items() if field.get("required") and not field.get("value")]
        if unfilled:
            return {
                "next_action": {"type": "manual", "reason": f"No values available for required fields: {', '.join(unfilled[:5])}"},
                "current_task": "browser_execution",
                "manual_required": True,
                "execution_history": execution_history + [
                    {
                        "step": "application_planner",
                        "status": "manual_required",
                        "action_type": "manual",
                        "reason": "no_values_for_remaining_required_fields",
                        "uids": unfilled[:10],
                    }
                ],
            }

        # Fallback: Observe again. Verification will enforce retry limits.
        return {
            "next_action": {"type": "observe"},
            "current_task": "browser_execution",
            "execution_history": execution_history + [
                {
                    "step": "application_planner",
                    "status": "planned",
                    "method": "heuristic",
                    "reason": "fallback_observe"
                }
            ]
        }

    def _field_has_actionable_value(self, state: ApplicationState, field: Dict) -> bool:
        field_type = field.get("type", "text")
        if field_type == "file":
            return bool(state.get("resume_pdf_path", ""))
        if field_type == "select":
            return True
        return bool(field.get("expected_value") or field.get("value") or self._infer_field_value(state, field))
    
    def _plan_fill_field(self, state: ApplicationState, uid: str, field: Dict) -> Dict[str, Any]:
        """Plan filling a specific field."""
        field_type = field.get("type", "text")
        expected_value = field.get("expected_value", field.get("value", ""))
        if not expected_value and field_type != "file":
            expected_value = self._infer_field_value(state, field)
        
        if field_type == "file":
            return self._plan_upload_file(state, uid)
        elif field_type == "select":
            return self._plan_select_field(state, uid, field)
        elif not expected_value:
            return {
                "next_action": {
                    "type": "manual",
                    "uid": uid,
                    "reason": f"No value available for field: {field.get('label', uid)}"
                },
                "current_task": "browser_execution",
                "manual_required": True,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "application_planner",
                        "status": "manual_required",
                        "action_type": "manual",
                        "uid": uid,
                        "label": field.get("label", ""),
                        "reason": "no_value_available"
                    }
                ]
            }
        else:
            return {
                "next_action": {
                    "type": "fill",
                    "uid": uid,
                    "value": expected_value
                },
                "current_task": "browser_execution",
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "application_planner",
                        "status": "planned",
                        "action_type": "fill",
                        "uid": uid,
                        "label": field.get("label", ""),
                        "value_preview": str(expected_value)[:80]
                    }
                ]
            }

    def _infer_field_value(self, state: ApplicationState, field: Dict) -> str:
        """Infer a field value from profile/resume data for common application fields."""
        label = f"{field.get('label', '')} {field.get('uid', '')}".lower()
        profile = state.get("user_profile", {}) or {}
        resume = state.get("resume_data", {}) or {}
        data = {**resume, **profile}

        candidates = []
        if any(k in label for k in ["name", "姓名", "full name"]):
            candidates = ["name", "full_name", "姓名"]
        elif any(k in label for k in ["email", "邮箱", "mail"]):
            candidates = ["email", "邮箱"]
        elif any(k in label for k in ["phone", "mobile", "电话", "手机"]):
            candidates = ["phone", "mobile", "telephone", "电话", "手机"]
        elif any(k in label for k in ["linkedin"]):
            candidates = ["linkedin", "linkedin_url"]
        elif any(k in label for k in ["github"]):
            candidates = ["github", "github_url"]

        for key in candidates:
            value = data.get(key)
            if value:
                return str(value)
        return ""
    
    def _plan_upload_file(self, state: ApplicationState, uid: str) -> Dict[str, Any]:
        """Plan file upload."""
        return {
            "next_action": {
                "type": "upload_file",
                "uid": uid,
                "file_path": state.get("resume_pdf_path", "")
            },
            "current_task": "browser_execution",
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "application_planner",
                    "status": "planned",
                    "action_type": "upload_file",
                    "uid": uid
                }
            ]
        }
    
    def _plan_select_field(self, state: ApplicationState, uid: str, field: Dict) -> Dict[str, Any]:
        """Plan selecting from dropdown."""
        return {
            "next_action": {
                "type": "click",
                "uid": uid,
                "reason": "Open dropdown for selection"
            },
            "current_task": "browser_execution",
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "application_planner",
                    "status": "planned",
                    "action_type": "click",
                    "uid": uid,
                    "reason": "dropdown"
                }
            ]
        }
    
    def _find_upload_field(self, application_form: Dict, nodes: List) -> Optional[str]:
        """Find file upload field."""
        for uid, field in application_form.items():
            if field.get("type") == "file" and not field.get("value"):
                return uid
        
        # Check node labels for upload indicators
        for node in nodes:
            label = str(node.get("label", "")).lower()
            if any(kw in label for kw in ["upload", "attach", "file", "resume", "简历"]):
                return node.get("uid")
        
        return None
    
    def _all_required_fields_filled(self, application_form: Dict) -> bool:
        """Check if all required fields are filled."""
        for field in application_form.values():
            if field.get("required") and not field.get("value"):
                return False
        return True
    
    def _build_planning_prompt(self, state: ApplicationState) -> str:
        """Build planning prompt for LLM."""
        form_fields = state.get("application_form", {})
        unfilled = [uid for uid, f in form_fields.items() if not f.get("value")]
        
        prompt = f"""Analyze the job application form state and decide the next action.

Current form fields:
- Form JSON: {json.dumps(form_fields, ensure_ascii=False)[:6000]}
- Unfilled: {unfilled}
- Total required: {len([f for f in form_fields.values() if f.get('required')])}
- Filled: {len([f for f in form_fields.values() if f.get('value')])}

User profile / resume data:
{json.dumps({'user_profile': state.get('user_profile', {}), 'resume_data': state.get('resume_data', {})}, ensure_ascii=False)[:8000]}

Recent execution history:
{chr(10).join([f"- {h.get('action_type', '?')}: {h.get('message', '')}" for h in state.get('execution_history', [])[-5:]])}

Provide the next action as a JSON object only:
{{
    "type": "observe|fill|click|upload_file|wait|done",
    "uid": "field_uid",
    "value": "value_to_fill",
    "reason": "explanation"
}}

Focus on:
1. Filling required fields first
2. Using available data from resume/profile. Do not return fill with empty value.
3. Handling select/dropdown fields with click first
4. Uploading resume when needed
5. Marking done when all filled
"""
        return prompt
    
    def _parse_plan_response(self, response: str) -> List[Dict]:
        """Parse LLM planning response."""
        try:
            import re
            # Extract JSON from response
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                action = json.loads(match.group())
                return [action] if action.get("type") else []
            return []
        except Exception:
            return []


def application_planner_node(state: ApplicationState) -> Dict[str, Any]:
    """Node wrapper for ApplicationPlannerNode."""
    planner = ApplicationPlannerNode(llm_client=None)
    return planner.plan(state)
