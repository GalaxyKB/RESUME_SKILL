"""Verify Result Node with visual verification support."""

import base64
from typing import Dict, Any, Optional, List
from .state import ApplicationState


class VerifyResultNode:
    """Verify browser execution results using visual inspection."""
    
    def __init__(self, vision_client=None):
        """Initialize with optional vision client (can be mocked for testing)."""
        self.vision_client = vision_client
    
    def verify(self, state: ApplicationState) -> Dict[str, Any]:
        """Verify the result of browser execution.
        
        Uses visual verification if vision_client is available,
        otherwise uses heuristic checks on browser context.
        """
        browser_context = state.get("browser_context", {})
        screenshot = browser_context.get("screenshot")
        snapshot = browser_context.get("snapshot")
        
        # Try visual verification first
        if self.vision_client and screenshot:
            try:
                return self._visual_verify(state, screenshot, snapshot)
            except Exception as e:
                print(f"[VerifyResultNode] Visual verification failed: {e}, falling back to heuristic")
        
        # Fallback to heuristic verification
        return self._heuristic_verify(state, snapshot)
    
    def _visual_verify(self, state: ApplicationState, screenshot: Any, snapshot: Any) -> Dict[str, Any]:
        """Perform visual verification using vision model."""
        try:
            # Prepare visual verification prompt
            execution_history = state.get("execution_history", [])
            job_description = state.get("job_description", {})
            
            prompt = self._build_verification_prompt(execution_history, job_description)
            
            # Call vision client to analyze screenshot
            verification_result = self.vision_client.verify_screenshot(
                screenshot=screenshot,
                prompt=prompt,
                context={
                    "snapshot": snapshot,
                    "execution_history": execution_history[-5:],  # Last 5 steps
                }
            )
            
            return self._process_verification_result(state, verification_result)
            
        except Exception as e:
            raise RuntimeError(f"Visual verification failed: {str(e)}")
    
    def _heuristic_verify(self, state: ApplicationState, snapshot: Any) -> Dict[str, Any]:
        """Perform heuristic verification without vision model."""
        errors = []
        warnings = []
        passed = True
        
        # Check 1: Snapshot exists and has content
        if not snapshot or not isinstance(snapshot, dict):
            errors.append("No snapshot available for verification")
            passed = False
        
        # Check 2: No error indicators in snapshot
        if snapshot:
            nodes = snapshot.get("nodes", [])
            for node in nodes:
                label = str(node.get("label", "")).lower()
                if any(err_word in label for err_word in ["error", "错误", "failed", "失败"]):
                    errors.append(f"Error indicator detected: {label}")
                    passed = False
        
        # Check 3: Expected fields filled (if we have form expectations)
        application_form = state.get("application_form", {})
        filled_fields = self._count_filled_fields(snapshot, application_form)
        
        if application_form and filled_fields < len(application_form) * 0.5:
            warnings.append(f"Only {filled_fields}/{len(application_form)} fields appear to be filled")
        
        # Determine retry strategy
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        
        if passed:
            return {
                "success": True,
                "gui_recovery_needed": False,
                "manual_required": False,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "verify_result",
                        "status": "verified",
                        "method": "heuristic",
                        "message": "Verification passed (heuristic)"
                    }
                ],
                "visual_verification_result": {
                    "passed": True,
                    "method": "heuristic",
                    "errors": errors,
                    "warnings": warnings,
                }
            }
        elif retry_count >= max_retries:
            return {
                "success": False,
                "manual_required": True,
                "gui_recovery_needed": False,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "verify_result",
                        "status": "failed",
                        "method": "heuristic",
                        "message": f"Verification failed after {max_retries} retries"
                    }
                ],
                "visual_verification_result": {
                    "passed": False,
                    "method": "heuristic",
                    "errors": errors,
                    "warnings": warnings,
                }
            }
        else:
            return {
                "success": False,
                "gui_recovery_needed": True,
                "retry_count": retry_count + 1,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "verify_result",
                        "status": "retry",
                        "method": "heuristic",
                        "message": f"Verification failed, retrying ({retry_count + 1}/{max_retries})"
                    }
                ],
                "visual_verification_result": {
                    "passed": False,
                    "method": "heuristic",
                    "errors": errors,
                    "warnings": warnings,
                }
            }
    
    def _process_verification_result(self, state: ApplicationState, result: Dict) -> Dict[str, Any]:
        """Process vision client verification result."""
        passed = result.get("passed", False)
        confidence = result.get("confidence", 0.0)
        details = result.get("details", "")
        
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        
        if passed and confidence >= 0.8:  # High confidence
            return {
                "success": True,
                "gui_recovery_needed": False,
                "manual_required": False,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "verify_result",
                        "status": "verified",
                        "method": "visual",
                        "confidence": confidence,
                        "message": details
                    }
                ],
                "visual_verification_result": result
            }
        elif passed and confidence >= 0.6:  # Medium confidence - alert user
            return {
                "success": True,
                "gui_recovery_needed": False,
                "manual_required": False,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "verify_result",
                        "status": "verified_with_warning",
                        "method": "visual",
                        "confidence": confidence,
                        "message": f"Verified with medium confidence: {details}"
                    }
                ],
                "visual_verification_result": result
            }
        elif retry_count >= max_retries:
            return {
                "success": False,
                "manual_required": True,
                "gui_recovery_needed": False,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "verify_result",
                        "status": "failed",
                        "method": "visual",
                        "confidence": confidence,
                        "message": f"Verification failed after {max_retries} retries: {details}"
                    }
                ],
                "visual_verification_result": result
            }
        else:
            return {
                "success": False,
                "gui_recovery_needed": True,
                "retry_count": retry_count + 1,
                "execution_history": state.get("execution_history", []) + [
                    {
                        "step": "verify_result",
                        "status": "retry",
                        "method": "visual",
                        "confidence": confidence,
                        "message": f"Verification uncertain, retrying ({retry_count + 1}/{max_retries}): {details}"
                    }
                ],
                "visual_verification_result": result
            }
    
    def _build_verification_prompt(self, execution_history: List, job_description: Dict) -> str:
        """Build prompt for vision model verification."""
        steps = []
        for entry in execution_history[-10:]:  # Last 10 steps
            if "action_type" in entry:
                steps.append(f"- {entry.get('action_type', 'unknown')}: {entry.get('message', '')}")
        
        job_title = job_description.get("title", "")
        company = job_description.get("company", "")
        
        prompt = f"""Verify the result of a job application form submission.

Context:
- Job: {job_title} at {company}
- Recent actions: {chr(10).join(steps)}

Please analyze the screenshot and determine:
1. Has the form been filled with appropriate data?
2. Are there any error messages visible?
3. Is there a confirmation message or success indicator?
4. Should the submission proceed?

Provide a structured response with:
- passed (bool): Whether verification passed
- confidence (0.0-1.0): Your confidence in the assessment
- details (str): Explanation of findings
"""
        return prompt
    
    def _count_filled_fields(self, snapshot: Any, expected_form: Dict) -> int:
        """Count filled fields in snapshot."""
        if not snapshot or not isinstance(snapshot, dict):
            return 0
        
        nodes = snapshot.get("nodes", [])
        filled_count = 0
        
        for node in nodes:
            value = node.get("value", "")
            placeholder = node.get("placeholder", "")
            
            # Consider field filled if it has value and value != placeholder
            if value and value != placeholder:
                filled_count += 1
        
        return filled_count


def verify_result_node(state: ApplicationState) -> Dict[str, Any]:
    """Node wrapper for VerifyResultNode."""
    verifier = VerifyResultNode(vision_client=None)
    return verifier.verify(state)
