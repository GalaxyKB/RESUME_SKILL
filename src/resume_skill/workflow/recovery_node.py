"""GUI Recovery Node for handling browser execution failures."""

import json
from typing import Dict, Any, Optional, List
from .state import ApplicationState


class GuiRecoveryNode:
    """Lightweight GUI recovery without Computer Use Agent."""
    
    MAX_RECOVERY_STEPS = 3
    
    def __init__(self, vision_client=None, chrome_client=None):
        self.vision_client = vision_client
        self.chrome_client = chrome_client
    
    def recover(self, state: ApplicationState) -> Dict[str, Any]:
        """Attempt to recover from execution failure."""
        errors = state.get("errors", [])
        browser_context = state.get("browser_context", {})
        execution_history = state.get("execution_history", [])
        
        if not errors:
            return {"gui_recovery_needed": False}
        
        # Get recovery actions from vision model
        recovery_actions = self._get_recovery_actions(state)
        
        if not recovery_actions:
            return {
                "manual_required": True,
                "gui_recovery_needed": False,
                "recovery_actions_executed": 0,
                "execution_history": execution_history + [
                    {"step": "gui_recovery", "status": "no_actions", "message": "No recovery actions available"}
                ]
            }
        
        # Execute recovery actions (max 3)
        result = {
            "execution_history": execution_history,
            "recovery_actions_executed": 0,
        }
        
        for i, action in enumerate(recovery_actions[:self.MAX_RECOVERY_STEPS]):
            if i >= self.MAX_RECOVERY_STEPS:
                break
            
            try:
                exec_result = self._execute_recovery_action(state, action)
                result["execution_history"].append(exec_result)
                result["recovery_actions_executed"] += 1
                
                if exec_result.get("status") == "error":
                    result["errors"] = state.get("errors", []) + [exec_result.get("error")]
                    
            except Exception as e:
                result["execution_history"].append({
                    "step": "gui_recovery",
                    "status": "action_error",
                    "action": action,
                    "error": str(e)
                })
                result["errors"] = state.get("errors", []) + [str(e)]
                break
        
        # Determine if manual intervention needed
        if result["recovery_actions_executed"] == 0 or "errors" in result:
            result["manual_required"] = True
            result["gui_recovery_needed"] = False
        else:
            result["gui_recovery_needed"] = False
        
        return result
    
    def _get_recovery_actions(self, state: ApplicationState) -> List[Dict]:
        """Get recovery actions from vision model."""
        if not self.vision_client:
            return self._fallback_recovery_actions(state)
        
        try:
            errors = state.get("errors", [])
            snapshot = state.get("browser_context", {}).get("snapshot", {})
            
            prompt = f"""Given these errors in a job application form:
{chr(10).join(errors[:3])}

Current snapshot indicates these fields/issues.
Provide up to 3 recovery actions as JSON array:
[
    {{"type": "click|type_text|press_key|upload_file", "uid": "field_id", "value": "...", "reason": "..."}}
]

Only return valid actions. Do NOT suggest submit buttons.
"""
            
            response = self.vision_client.get_recovery_actions(
                snapshot=snapshot,
                errors=errors,
                prompt=prompt
            )
            
            # Parse JSON response
            actions = json.loads(response)
            
            # Validate actions
            valid_actions = []
            for action in actions:
                if self._validate_recovery_action(action):
                    valid_actions.append(action)
            
            return valid_actions[:self.MAX_RECOVERY_STEPS]
            
        except Exception as e:
            print(f"[GuiRecoveryNode] Vision model error: {e}, using fallback")
            return self._fallback_recovery_actions(state)
    
    def _fallback_recovery_actions(self, state: ApplicationState) -> List[Dict]:
        """Fallback heuristic recovery actions."""
        errors = state.get("errors", [])
        actions = []
        
        # Analyze error patterns
        for error in errors[:3]:
            error_lower = error.lower()
            
            # Dropdown errors
            if "dropdown" in error_lower or "select" in error_lower:
                actions.append({
                    "type": "click",
                    "uid": "dropdown_field",
                    "reason": "Open dropdown menu"
                })
            
            # Fill errors
            elif "fill" in error_lower or "empty" in error_lower:
                actions.append({
                    "type": "type_text",
                    "uid": "text_field",
                    "value": "retry_value",
                    "reason": "Retry field input"
                })
            
            # Upload errors
            elif "upload" in error_lower or "file" in error_lower:
                actions.append({
                    "type": "upload_file",
                    "uid": "file_input",
                    "reason": "Retry file upload"
                })
            
            # Key press for validation
            elif "submit" not in error_lower:
                actions.append({
                    "type": "press_key",
                    "value": "Tab",
                    "reason": "Trigger validation"
                })
        
        return actions[:self.MAX_RECOVERY_STEPS]
    
    def _execute_recovery_action(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Execute a single recovery action."""
        action_type = action.get("type")
        uid = action.get("uid")
        value = action.get("value", "")
        reason = action.get("reason", "")
        
        if not self.chrome_client:
            return {
                "step": "gui_recovery",
                "status": "skipped",
                "action": action,
                "reason": "No chrome client"
            }
        
        try:
            if action_type == "click":
                # Prevent auto-submit
                if self._is_forbidden_button(uid):
                    return {
                        "step": "gui_recovery",
                        "status": "blocked",
                        "action": action,
                        "reason": "Blocked submit button"
                    }
                
                self.chrome_client.call_tool("click", {"uid": uid})
                return {
                    "step": "gui_recovery",
                    "status": "completed",
                    "action_type": "click",
                    "uid": uid,
                    "reason": reason
                }
            
            elif action_type == "type_text":
                self.chrome_client.call_tool("type_text", {"uid": uid, "text": value})
                return {
                    "step": "gui_recovery",
                    "status": "completed",
                    "action_type": "type_text",
                    "uid": uid,
                    "reason": reason
                }
            
            elif action_type == "press_key":
                self.chrome_client.call_tool("press_key", {"key": value})
                return {
                    "step": "gui_recovery",
                    "status": "completed",
                    "action_type": "press_key",
                    "key": value,
                    "reason": reason
                }
            
            elif action_type == "upload_file":
                file_path = value or state.get("resume_pdf_path", "")
                self.chrome_client.call_tool("upload_file", {
                    "uid": uid,
                    "filePath": file_path
                })
                return {
                    "step": "gui_recovery",
                    "status": "completed",
                    "action_type": "upload_file",
                    "uid": uid,
                    "reason": reason
                }
            
            else:
                return {
                    "step": "gui_recovery",
                    "status": "error",
                    "error": f"Unknown action type: {action_type}"
                }
        
        except Exception as e:
            return {
                "step": "gui_recovery",
                "status": "error",
                "action": action,
                "error": str(e)
            }
    
    def _validate_recovery_action(self, action: Dict) -> bool:
        """Validate recovery action."""
        action_type = action.get("type")
        valid_types = {"click", "type_text", "press_key", "upload_file"}
        
        if action_type not in valid_types:
            return False
        
        # Prevent submit actions
        if action_type == "click" and self._is_forbidden_button(action.get("uid", "")):
            return False
        
        return True
    
    def _is_forbidden_button(self, uid: str) -> bool:
        """Check if button is forbidden."""
        forbidden_keywords = {
            "submit", "提交", "投递", "apply", "应聘",
            "final", "最后", "完成", "确认", "send"
        }
        uid_lower = str(uid).lower()
        return any(kw in uid_lower for kw in forbidden_keywords)


def gui_recovery_node(state: ApplicationState) -> Dict[str, Any]:
    """Node wrapper for GuiRecoveryNode."""
    recovery = GuiRecoveryNode(vision_client=None, chrome_client=None)
    result = recovery.recover(state)
    
    # Add default values
    if "gui_recovery_needed" not in result:
        result["gui_recovery_needed"] = False
    
    return result
