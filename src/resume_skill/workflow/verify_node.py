"""Verify Result Node with vision model verification."""

import json
from typing import Dict, Any, Optional, List
from .state import ApplicationState


class VerifyResultNode:
    """Verify browser execution results using vision model."""
    
    def __init__(self, vision_client=None):
        if vision_client and not hasattr(vision_client, "verify"):
            try:
                from resume_skill.llm.vision import VisionWorkflowAdapter

                vision_client = VisionWorkflowAdapter(vision_client)
            except Exception:
                pass
        self.vision_client = vision_client
    
    def verify(self, state: ApplicationState) -> Dict[str, Any]:
        """Verify execution results using vision model."""
        browser_context = state.get("browser_context", {})
        snapshot = browser_context.get("snapshot")
        screenshot = browser_context.get("screenshot")
        execution_history = state.get("execution_history", [])
        
        if not screenshot and not snapshot:
            return self._handle_no_context(state)
        
        if not self.vision_client:
            return self._heuristic_verify(state)
        
        try:
            # Build verification prompt
            last_action = execution_history[-1] if execution_history else {}
            prompt = self._build_prompt(state, last_action)
            
            # Call vision model
            response = self.vision_client.verify(
                screenshot=screenshot,
                snapshot=snapshot,
                prompt=prompt
            )
            
            # Parse and process response
            return self._process_vision_response(state, response, last_action)
            
        except json.JSONDecodeError as e:
            fallback = self._heuristic_verify(state)
            fallback["errors"] = state.get("errors", []) + [f"Vision JSON parse error, used heuristic fallback: {e}"]
            fallback["gui_recovery_needed"] = True
            return fallback
        except Exception as e:
            fallback = self._heuristic_verify(state)
            fallback["errors"] = state.get("errors", []) + [f"Verification error, used heuristic fallback: {e}"]
            return fallback
    
    def _build_prompt(self, state: ApplicationState, last_action: Dict) -> str:
        """Build verification prompt for vision model."""
        action_type = last_action.get("action_type", "unknown")
        uid = last_action.get("uid", "")
        value = last_action.get("value", "")
        
        expected_fields = state.get("application_form", {})
        execution_steps = "\n".join([
            f"- {h.get('action_type', 'unknown')}: {h.get('message', '')}"
            for h in state.get("execution_history", [])[-5:]
        ])
        
        prompt = f"""Analyze the job application form state after this action:
- Action: {action_type} on uid={uid} with value={value}
- Recent steps: {execution_steps}

Provide a JSON response with this EXACT structure:
{{
    "action_success": true/false,
    "page_success": true/false,
    "summary": "brief description",
    "issues": [
        {{"uid": "field_id", "label": "Field Name", "problem": "...", "suggestion": "..."}}
    ],
    "next_actions": [
        {{"type": "click|type_text|press_key|upload_file", "uid": "...", "reason": "..."}}
    ],
    "manual_required": false
}}

- action_success: Did the last action complete correctly?
- page_success: Is the form fully filled and ready to submit?
- issues: List any problems found
- next_actions: Suggested recovery actions (up to 3)
- manual_required: Does this need manual intervention?
"""
        return prompt
    
    def _process_vision_response(self, state: ApplicationState, response: str, 
                                  last_action: Dict) -> Dict[str, Any]:
        """Process vision model response."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise
        
        action_success = data.get("action_success", False)
        page_success = data.get("page_success", False)
        manual_required = data.get("manual_required", False)
        next_actions = data.get("next_actions", [])
        issues = data.get("issues", [])
        summary = data.get("summary", "")
        
        result = {
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "verify_result",
                    "status": "verified" if action_success else "failed",
                    "action_success": action_success,
                    "page_success": page_success,
                    "summary": summary,
                    "issues_count": len(issues),
                }
            ],
            "visual_verification_result": {
                "action_success": action_success,
                "page_success": page_success,
                "summary": summary,
                "issues": issues,
                "next_actions": next_actions,
            }
        }
        
        # Mark fields as verified if action succeeded
        if action_success and "uid" in last_action:
            uid = last_action["uid"]
            application_form = state.get("application_form", {})
            if uid in application_form:
                application_form[uid]["verified"] = True
                result["application_form"] = application_form
        
        # Set page success
        if page_success:
            result["success"] = True
        
        # Handle recovery needs
        if action_success == False and next_actions:
            result["gui_recovery_needed"] = True
            result["next_actions"] = next_actions
        
        # Handle manual requirement
        if manual_required:
            result["manual_required"] = True
        
        return result
    
    def _heuristic_verify(self, state: ApplicationState) -> Dict[str, Any]:
        """Fallback heuristic verification without vision model."""
        snapshot = state.get("browser_context", {}).get("snapshot", {})
        application_form = state.get("application_form", {})
        
        errors = []
        filled_count = 0
        
        # Check snapshot for errors
        nodes = snapshot.get("nodes", []) if isinstance(snapshot, dict) else []
        for node in nodes:
            label = str(node.get("label", "")).lower()
            if any(err in label for err in ["error", "错误", "failed", "失败"]):
                errors.append(f"Error: {label}")
        
        # Count filled fields
        for uid, field in application_form.items():
            if field.get("value"):
                filled_count += 1
        
        # Determine success
        total_required = len([f for f in application_form.values() 
                             if f.get("required", False)])
        filled_required = len([f for f in application_form.values() 
                              if f.get("required", False) and f.get("value")])
        
        page_success = filled_required == total_required if total_required > 0 else True
        
        return {
            "success": page_success,
            "gui_recovery_needed": len(errors) > 0,
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "verify_result",
                    "status": "heuristic_verified",
                    "filled": filled_count,
                    "total": len(application_form),
                    "errors": len(errors)
                }
            ],
            "errors": state.get("errors", []) + errors,
        }
    
    def _handle_json_error(self, state: ApplicationState, error: str) -> Dict[str, Any]:
        """Handle JSON parse error."""
        return {
            "errors": state.get("errors", []) + [f"Vision JSON parse error: {error}"],
            "gui_recovery_needed": True,
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "verify_result",
                    "status": "error",
                    "error": "JSON parse failed"
                }
            ]
        }
    
    def _handle_error(self, state: ApplicationState, error: str) -> Dict[str, Any]:
        """Handle general error."""
        return {
            "errors": state.get("errors", []) + [f"Verification error: {error}"],
            "gui_recovery_needed": True,
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "verify_result",
                    "status": "error",
                    "error": error
                }
            ]
        }
    
    def _handle_no_context(self, state: ApplicationState) -> Dict[str, Any]:
        """Handle missing screenshot/snapshot."""
        return {
            "success": False,
            "errors": state.get("errors", []) + ["No screenshot or snapshot available"],
            "gui_recovery_needed": True,
            "execution_history": state.get("execution_history", []) + [
                {
                    "step": "verify_result",
                    "status": "skipped",
                    "reason": "No visual context"
                }
            ]
        }


def verify_result_node(state: ApplicationState) -> Dict[str, Any]:
    """Node wrapper for VerifyResultNode."""
    verifier = VerifyResultNode(vision_client=None)
    return verifier.verify(state)
