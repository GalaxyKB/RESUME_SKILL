"""
ApplicationPlannerNode - LLM-based planner for form filling strategy.
Text model is the primary decision maker.
"""

import json
import re
from typing import Any, Dict, Optional
from datetime import datetime

from ..config import CONFIG
from ..llm.factory import create_llm_client


class ApplicationPlannerNode:
    """LLM-based planner node for determining next action in form filling."""
    
    def __init__(self):
        self.llm = None
        self.last_error = None
    
    def initialize(self):
        """Initialize LLM client."""
        try:
            self.llm = create_llm_client()
        except Exception as e:
            self.last_error = f"Failed to initialize LLM: {e}"
            raise
    
    def plan(self, state: Any) -> Dict[str, Any]:
        """
        Plan next action based on state.
        
        Args:
            state: ApplicationState with user_profile, application_form, etc.
            
        Returns:
            Updated state with next_action set
        """
        if not self.llm:
            self.initialize()
        
        try:
            # Build planning prompt
            prompt = self._build_prompt(state)
            
            # Call LLM
            response = self.llm.call_text(
                system="You are an expert form filling assistant. Return only valid JSON.",
                user_message=prompt
            )
            
            # Parse response
            action = self._parse_action(response, state)
            
            # Update state
            state.next_action = action
            if "reason" in action:
                state.add_log(f"Planner: {action.get('type', 'unknown')} - {action['reason'][:60]}")
            
            return state
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # Error handling
            state.errors.append(f"Planner error: {e}")
            state.add_log(f"Planner failed: {e}")
            
            # Fallback to manual
            state.next_action = {
                "type": "manual",
                "reason": "planner error - manual intervention required",
                "error": str(e)
            }
            
            return state
    
    def _build_prompt(self, state: Any) -> str:
        """Build comprehensive prompt for LLM planning."""
        
        # Get current form fields
        fields_info = self._format_fields(state.fields) if state.fields else "No fields found"
        
        # Get user profile summary
        profile_info = self._format_profile(state.user_profile)
        
        # Get browser context
        browser_info = self._format_browser_context(state.browser_context if hasattr(state, 'browser_context') else {})
        
        # Get execution history
        history_info = self._format_history(state.execution_history if hasattr(state, 'execution_history') else [])
        
        prompt = f"""You are an expert web form filling assistant. Analyze the following information and return the SINGLE BEST next action to take.

## User Profile
{profile_info}

## Current Form Fields Available
{fields_info}

## Browser Context (Page Snapshot)
{browser_info}

## Execution History (Previous Actions)
{history_info}

## Decision Rules
1. **Text Fields (普通文本框)**: Use "fill" action
   - For name, email, phone, address, education info, etc.
   - Can use fill_form for multiple stable text fields if there are 2+ consecutive fillable fields

2. **File/Upload Fields**: Use "upload_file" action
   - For resume, attachment, file upload, 简历上传, etc.
   - Provide file path if available in state.resume_pdf_path

3. **Dropdowns/Select/Custom Controls**: Use "click" action first
   - Click to expand/open the control
   - DO NOT try to fill dropdowns directly
   - Find the selector/uid of the dropdown element

4. **Sensitive Fields**: Use "manual" action
   - For password, verification code, ID number, etc.
   - When confidence is low or unsure

5. **Observation Actions**: Use "observe" action
   - If page layout unclear
   - If needed to refresh form structure
   - If form appears to have loaded incompletely

6. **Completion**: Use "done" action
   - Only when ALL required fields are visually confirmed as complete
   - When there are no more fields to fill
   - When form is ready for submission

## Action Format
Return ONLY a valid JSON object (no markdown, no explanation):
{{
  "type": "fill" | "fill_form" | "click" | "upload_file" | "manual" | "observe" | "done",
  "uid": "field_unique_id",
  "value": "value_to_fill_or_target_selector",
  "target": "field_label_or_name",
  "reason": "brief_explanation",
  "confidence": 0.0-1.0
}}

## Important Notes
- Return ONLY ONE action at a time
- Do NOT fill the entire form in one action
- Focus on the most important/first unfilled field
- Be conservative: prefer "manual" or "click" over guessing
- For dropdowns: use "click" to expand first, then analyze options
- Always provide a clear reason for the action

Now analyze the form and return the next best action:"""
        
        return prompt
    
    def _format_fields(self, fields: list) -> str:
        """Format form fields for prompt."""
        if not fields:
            return "No fields found"
        
        lines = []
        for f in fields[:15]:  # Limit to first 15 fields
            uid = f.get("uid", "unknown")
            label = f.get("label", "")
            field_type = f.get("type", "text")
            filled = f.get("filled", False)
            value = f.get("value", "") or f.get("answer", "")
            
            status = "✓ FILLED" if filled else "□ EMPTY"
            value_str = f" = {value[:30]}" if value else ""
            
            lines.append(f"  [{uid}] {label} ({field_type}) {status}{value_str}")
        
        return "\n".join(lines)
    
    def _format_profile(self, profile: Dict[str, Any]) -> str:
        """Format user profile for prompt."""
        if not profile:
            return "No profile loaded"
        
        lines = []
        
        # Personal info
        personal = profile.get("personal", {}) or {}
        if personal:
            lines.append("Personal Information:")
            if personal.get("name_cn"):
                lines.append(f"  - Name: {personal['name_cn']}")
            if personal.get("email"):
                lines.append(f"  - Email: {personal['email']}")
            if personal.get("phone"):
                lines.append(f"  - Phone: {personal['phone']}")
            if personal.get("location"):
                lines.append(f"  - Location: {personal['location']}")
        
        # Education
        education = profile.get("education", []) or []
        if education:
            lines.append("Education:")
            for edu in education[:2]:
                school = edu.get("school", "")
                degree = edu.get("degree", "")
                major = edu.get("major", "")
                if school:
                    lines.append(f"  - {school} | {degree} | {major}")
        
        # Experience
        experience = profile.get("experience", []) or []
        if experience:
            lines.append("Work Experience:")
            for exp in experience[:2]:
                company = exp.get("company", "")
                position = exp.get("position", "")
                if company:
                    lines.append(f"  - {company} | {position}")
        
        return "\n".join(lines) if lines else "No profile info available"
    
    def _format_browser_context(self, context: Dict[str, Any]) -> str:
        """Format browser context for prompt."""
        if not context:
            return "No context available"
        
        snapshot = context.get("snapshot", "")
        if snapshot:
            # Truncate to first 1000 chars
            return snapshot[:1000] + "..." if len(snapshot) > 1000 else snapshot
        
        return "No snapshot available"
    
    def _format_history(self, history: list) -> str:
        """Format execution history for prompt."""
        if not history:
            return "No previous actions"
        
        lines = []
        for action in history[-5:]:  # Last 5 actions
            timestamp = action.get("timestamp", "")
            action_type = action.get("type", "")
            target = action.get("target", "")
            status = action.get("status", "")
            
            lines.append(f"  - [{timestamp}] {action_type} on {target}: {status}")
        
        return "\n".join(lines)
    
    def _parse_action(self, response: str, state: Any) -> Dict[str, Any]:
        """
        Parse LLM response into action.
        
        Args:
            response: LLM response text
            state: Current application state
            
        Returns:
            Parsed action dictionary
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            
            if not json_match:
                # If no JSON found, check for common patterns
                response_lower = response.lower()
                
                if "fill" in response_lower and "dropdown" not in response_lower:
                    return {
                        "type": "fill",
                        "reason": "Inferred from response - text field filling",
                        "raw_response": response[:100]
                    }
                elif "upload" in response_lower or "file" in response_lower or "resume" in response_lower:
                    return {
                        "type": "upload_file",
                        "reason": "Inferred from response - file upload detected",
                        "raw_response": response[:100]
                    }
                elif "click" in response_lower or "dropdown" in response_lower or "select" in response_lower:
                    return {
                        "type": "click",
                        "reason": "Inferred from response - click/expand action",
                        "raw_response": response[:100]
                    }
                elif "done" in response_lower or "complete" in response_lower or "finish" in response_lower:
                    return {
                        "type": "done",
                        "reason": "Inferred from response - form complete",
                        "raw_response": response[:100]
                    }
                
                # Default to manual if can't parse
                state.errors.append("No JSON found in LLM response")
                return {
                    "type": "manual",
                    "reason": "planner JSON parse failed - no valid JSON in response",
                    "raw_response": response[:100]
                }
            
            # Parse JSON
            json_str = json_match.group()
            action = json.loads(json_str)
            
            # Validate action type
            valid_types = ["fill", "fill_form", "click", "upload_file", "manual", "observe", "done"]
            if action.get("type") not in valid_types:
                state.errors.append(f"Invalid action type: {action.get('type')}")
                return {
                    "type": "manual",
                    "reason": f"Invalid action type: {action.get('type')}",
                    "raw_response": response[:100]
                }
            
            # Add timestamp
            action["timestamp"] = datetime.now().isoformat()
            
            return action
            
        except json.JSONDecodeError as e:
            state.errors.append(f"JSON parse error: {e}")
            return {
                "type": "manual",
                "reason": "planner JSON parse failed - invalid JSON format",
                "error": str(e),
                "raw_response": response[:100] if response else ""
            }
        except Exception as e:
            state.errors.append(f"Parse error: {e}")
            return {
                "type": "manual",
                "reason": "planner JSON parse failed - unexpected error",
                "error": str(e),
                "raw_response": response[:100] if response else ""
            }


# Global planner instance
_planner_instance = None


def get_planner() -> ApplicationPlannerNode:
    """Get or create planner instance."""
    global _planner_instance
    if _planner_instance is None:
        _planner_instance = ApplicationPlannerNode()
        _planner_instance.initialize()
    return _planner_instance


def plan_next_action(state: Any) -> Any:
    """
    Public API to plan next action.
    
    Args:
        state: ApplicationState
        
    Returns:
        Updated ApplicationState
    """
    planner = get_planner()
    return planner.plan(state)
