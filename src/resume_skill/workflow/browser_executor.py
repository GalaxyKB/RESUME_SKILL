"""Browser executor node for LangGraph workflow."""

import time
from typing import Dict, Any, Optional, List
from .state import ApplicationState


class BrowserExecutorNode:
    """Execute browser actions via Chrome DevTools MCP."""
    
    # Forbidden button keywords that should not be auto-clicked
    FORBIDDEN_SUBMIT_KEYWORDS = {
        "submit", "提交", "投递", "apply", "应聘", 
        "final", "最后", "完成", "确认", "send"
    }
    
    def __init__(self, chrome_client=None):
        """Initialize with optional Chrome client (can be mocked for testing)."""
        self.chrome = chrome_client
    
    def execute(self, state: ApplicationState) -> Dict[str, Any]:
        """Execute the next action in the workflow."""
        next_action = state.get("next_action", "")
        
        if not next_action or not isinstance(next_action, dict):
            return {
                "errors": state.get("errors", []) + ["Invalid next_action format"],
                "gui_recovery_needed": True,
            }
        
        action_type = next_action.get("type", "observe")
        
        try:
            if action_type == "observe":
                return self._action_observe(state, next_action)
            elif action_type == "fill":
                return self._action_fill(state, next_action)
            elif action_type == "fill_form":
                return self._action_fill_form(state, next_action)
            elif action_type == "click":
                return self._action_click(state, next_action)
            elif action_type == "upload_file":
                return self._action_upload_file(state, next_action)
            elif action_type == "type_text":
                return self._action_type_text(state, next_action)
            elif action_type == "press_key":
                return self._action_press_key(state, next_action)
            elif action_type == "wait":
                return self._action_wait(state, next_action)
            elif action_type == "manual":
                return self._action_manual(state, next_action)
            elif action_type == "done":
                return self._action_done(state, next_action)
            else:
                error = f"Unknown action type: {action_type}"
                return self._handle_error(state, error)
                
        except Exception as e:
            error = f"Action {action_type} failed: {str(e)}"
            return self._handle_error(state, error)
    
    def _action_observe(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Observe the current page state."""
        try:
            if not self.chrome:
                raise RuntimeError("Chrome client not initialized")
            
            # Take snapshot and screenshot
            snapshot = self.chrome.call_tool("take_snapshot", {})
            screenshot = self.chrome.call_tool("take_screenshot", {})
            
            browser_context = state.get("browser_context", {})
            browser_context["snapshot"] = snapshot
            browser_context["screenshot"] = screenshot
            
            return {
                "browser_context": browser_context,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.observe",
                        "status": "completed",
                        "action_type": "observe",
                        "message": "Captured page snapshot and screenshot"
                    }
                ]
            }
        except Exception as e:
            return self._handle_error(state, f"Observe failed: {str(e)}")
    
    def _action_fill(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Fill a single form field."""
        uid = action.get("uid")
        value = action.get("value", "")
        
        if not uid:
            return self._handle_error(state, "Fill action missing uid")
        
        try:
            if not self.chrome:
                raise RuntimeError("Chrome client not initialized")
            
            self.chrome.call_tool("fill", {"uid": uid, "value": value})
            
            return {
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.fill",
                        "status": "completed",
                        "action_type": "fill",
                        "uid": uid,
                        "value": value[:50] + "..." if len(str(value)) > 50 else value
                    }
                ]
            }
        except Exception as e:
            return self._handle_error(state, f"Fill failed: {str(e)}")
    
    def _action_fill_form(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Fill multiple form fields."""
        elements = action.get("elements", [])
        
        if not elements:
            return self._handle_error(state, "fill_form action missing elements")
        
        try:
            if not self.chrome:
                raise RuntimeError("Chrome client not initialized")
            
            self.chrome.call_tool("fill_form", {"elements": elements})
            
            return {
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.fill_form",
                        "status": "completed",
                        "action_type": "fill_form",
                        "element_count": len(elements)
                    }
                ]
            }
        except Exception as e:
            return self._handle_error(state, f"Fill form failed: {str(e)}")
    
    def _action_click(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Click an element."""
        uid = action.get("uid")
        
        if not uid:
            return self._handle_error(state, "Click action missing uid")
        
        # Check if this is a forbidden submit button
        if self._is_forbidden_submit(uid) and not state.get("allow_submit", False):
            error = f"Blocked auto-click on forbidden button: {uid}"
            return {
                "manual_required": True,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.click",
                        "status": "blocked",
                        "action_type": "click",
                        "uid": uid,
                        "reason": error
                    }
                ]
            }
        
        try:
            if not self.chrome:
                raise RuntimeError("Chrome client not initialized")
            
            self.chrome.call_tool("click", {"uid": uid})
            
            return {
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.click",
                        "status": "completed",
                        "action_type": "click",
                        "uid": uid
                    }
                ]
            }
        except Exception as e:
            return self._handle_error(state, f"Click failed: {str(e)}")
    
    def _action_upload_file(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Upload a file to a form field."""
        uid = action.get("uid")
        file_path = action.get("file_path")
        
        if not uid:
            return self._handle_error(state, "upload_file action missing uid")
        
        # If no file_path specified, try to use resume_pdf_path
        if not file_path:
            file_path = state.get("resume_pdf_path", "")
        
        if not file_path:
            return self._handle_error(state, "upload_file missing file_path and resume_pdf_path")
        
        try:
            if not self.chrome:
                raise RuntimeError("Chrome client not initialized")
            
            self.chrome.call_tool("upload_file", {"uid": uid, "filePath": file_path})
            
            return {
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.upload_file",
                        "status": "completed",
                        "action_type": "upload_file",
                        "uid": uid,
                        "file_path": file_path
                    }
                ]
            }
        except Exception as e:
            return self._handle_error(state, f"Upload file failed: {str(e)}")
    
    def _action_type_text(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Type text (placeholder for future implementation)."""
        uid = action.get("uid")
        value = action.get("value", "")
        
        try:
            if not self.chrome:
                raise RuntimeError("Chrome client not initialized")
            
            # Call type_text tool if available
            self.chrome.call_tool("type_text", {"uid": uid, "text": value})
            
            return {
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.type_text",
                        "status": "completed",
                        "action_type": "type_text",
                        "uid": uid
                    }
                ]
            }
        except Exception as e:
            return self._handle_error(state, f"Type text failed: {str(e)}")
    
    def _action_press_key(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Press a keyboard key."""
        key = action.get("value", "Enter")
        
        try:
            if not self.chrome:
                raise RuntimeError("Chrome client not initialized")
            
            # Call press_key tool if available
            self.chrome.call_tool("press_key", {"key": key})
            
            return {
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.press_key",
                        "status": "completed",
                        "action_type": "press_key",
                        "key": key
                    }
                ]
            }
        except Exception as e:
            return self._handle_error(state, f"Press key failed: {str(e)}")
    
    def _action_wait(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Wait for a specified time or condition."""
        duration = action.get("value", 1)
        if duration in ("", None):
            duration = 1
        
        try:
            # Wait using time.sleep (simple approach)
            # In production, could use wait_for selector or similar
            duration_seconds = max(0.0, min(float(duration), 10.0))
            time.sleep(duration_seconds)
            
            return {
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "browser_executor.wait",
                        "status": "completed",
                        "action_type": "wait",
                        "duration": duration_seconds
                    }
                ]
            }
        except Exception as e:
            return self._handle_error(state, f"Wait failed: {str(e)}")
    
    def _action_manual(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Mark action as requiring manual intervention."""
        reason = action.get("reason", "Manual intervention required")
        
        return {
            "manual_required": True,
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "browser_executor.manual",
                    "status": "manual_intervention",
                    "action_type": "manual",
                    "reason": reason
                }
            ]
        }
    
    def _action_done(self, state: ApplicationState, action: Dict) -> Dict[str, Any]:
        """Mark workflow as complete."""
        form = state.get("application_form", {})
        has_workflow_context = bool(form or state.get("browser_context"))
        history = state.get("execution_history", [])
        has_write_action = any(
            item.get("step") in {"browser_executor.fill", "browser_executor.upload_file", "browser_executor.type_text"}
            and item.get("status") == "completed"
            for item in history
        )
        if has_workflow_context and (
            not form
            or any(field.get("required") and not field.get("value") for field in form.values())
            or not has_write_action
        ):
            return self._handle_error(state, "Done blocked: form is not filled or no write action was executed")

        return {
            "success": True,
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "browser_executor.done",
                    "status": "success",
                    "action_type": "done",
                    "message": "Workflow completed successfully"
                }
            ]
        }
    
    def _is_forbidden_submit(self, uid: str) -> bool:
        """Check if uid is a forbidden submit button."""
        uid_lower = str(uid).lower()
        for keyword in self.FORBIDDEN_SUBMIT_KEYWORDS:
            if keyword in uid_lower:
                return True
        return False
    
    def _handle_error(self, state: ApplicationState, error: str) -> Dict[str, Any]:
        """Handle action execution error."""
        return {
            "errors": state.get("errors", []) + [error],
            "gui_recovery_needed": True,
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "browser_executor",
                    "status": "error",
                    "message": error
                }
            ]
        }


def browser_executor_node(state: ApplicationState) -> Dict[str, Any]:
    """Node wrapper for BrowserExecutorNode."""
    executor = BrowserExecutorNode()
    return executor.execute(state)
