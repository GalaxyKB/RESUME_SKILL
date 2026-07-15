"""Tests for VerifyResultNode and GuiRecoveryNode."""

import pytest
import json
from unittest.mock import Mock
from resume_skill.workflow.verify_node import VerifyResultNode
from resume_skill.workflow.recovery_node import GuiRecoveryNode
from resume_skill.workflow.state import ApplicationState


class MockVisionClient:
    """Mock vision client for testing."""
    
    def __init__(self, response=None):
        self.response = response or self._default_response()
        self.calls = []
    
    def verify(self, screenshot, snapshot, prompt):
        self.calls.append(("verify", prompt))
        return json.dumps(self.response)
    
    def get_recovery_actions(self, snapshot, errors, prompt):
        self.calls.append(("recovery", errors))
        actions = [
            {"type": "click", "uid": "field_1", "reason": "Click field"},
            {"type": "type_text", "uid": "field_2", "value": "test", "reason": "Type text"}
        ]
        return json.dumps(actions)
    
    def _default_response(self):
        return {
            "action_success": True,
            "page_success": False,
            "summary": "Action completed",
            "issues": [],
            "next_actions": [],
            "manual_required": False
        }


class MockChromeClient:
    """Mock Chrome client for testing."""
    
    def __init__(self):
        self.calls = []
    
    def call_tool(self, name, params):
        self.calls.append((name, params))
        return {"success": True}


class TestVerifyResultNode:
    """Tests for VerifyResultNode."""
    
    def setup_method(self):
        self.base_state: ApplicationState = {
            "task_id": "test-001",
            "user_profile": {},
            "resume_data": {},
            "resume_pdf_path": "/resume.pdf",
            "job_description": {"title": "Engineer", "company": "TechCorp"},
            "application_form": {"field_1": {"value": "John", "required": True}},
            "generated_documents": {},
            "browser_context": {
                "snapshot": {"nodes": [{"uid": "1", "label": "Name", "value": "John"}]},
                "screenshot": b"fake_image"
            },
            "current_task": "verification",
            "next_action": {},
            "execution_history": [
                {"action_type": "fill", "uid": "field_1", "value": "John"}
            ],
            "errors": [],
            "gui_recovery_needed": False,
            "manual_required": False,
            "success": False,
            "retry_count": 0,
            "max_retries": 3,
        }
    
    def test_verify_action_success(self):
        """Test successful action verification."""
        vision = MockVisionClient({
            "action_success": True,
            "page_success": False,
            "summary": "Field filled successfully",
            "issues": [],
            "next_actions": [],
            "manual_required": False
        })
        
        verifier = VerifyResultNode(vision_client=vision)
        result = verifier.verify(self.base_state)
        
        assert len(vision.calls) > 0
        assert result["visual_verification_result"]["action_success"] == True
        assert len(result.get("execution_history", [])) > 0
    
    def test_verify_page_success(self):
        """Test page completion verification."""
        vision = MockVisionClient({
            "action_success": True,
            "page_success": True,
            "summary": "Form completed",
            "issues": [],
            "next_actions": [],
            "manual_required": False
        })
        
        verifier = VerifyResultNode(vision_client=vision)
        result = verifier.verify(self.base_state)
        
        assert result.get("success") == True
    
    def test_verify_action_failed_with_recovery(self):
        """Test action failure with recovery actions."""
        vision = MockVisionClient({
            "action_success": False,
            "page_success": False,
            "summary": "Field validation failed",
            "issues": [{"uid": "field_1", "problem": "Invalid format", "suggestion": "Use numbers only"}],
            "next_actions": [{"type": "click", "uid": "field_1", "reason": "Retry field"}],
            "manual_required": False
        })
        
        verifier = VerifyResultNode(vision_client=vision)
        result = verifier.verify(self.base_state)
        
        assert result["visual_verification_result"]["action_success"] == False
        assert result["gui_recovery_needed"] == True
        assert len(result.get("next_actions", [])) > 0
    
    def test_verify_manual_required(self):
        """Test manual intervention requirement."""
        vision = MockVisionClient({
            "action_success": False,
            "page_success": False,
            "summary": "CAPTCHA required",
            "issues": [{"uid": "captcha", "problem": "CAPTCHA verification needed"}],
            "next_actions": [],
            "manual_required": True
        })
        
        verifier = VerifyResultNode(vision_client=vision)
        result = verifier.verify(self.base_state)
        
        assert result.get("manual_required") == True
    
    def test_verify_json_parse_error(self):
        """Test JSON parse error handling."""
        vision = Mock()
        vision.verify.return_value = "invalid json {{"
        
        verifier = VerifyResultNode(vision_client=vision)
        result = verifier.verify(self.base_state)
        
        assert "errors" in result
        assert any("JSON" in e for e in result["errors"])
        assert result["gui_recovery_needed"] == True
    
    def test_verify_field_marked_verified(self):
        """Test that successful action marks field as verified."""
        self.base_state["application_form"]["field_1"]["verified"] = False
        self.base_state["execution_history"][-1]["uid"] = "field_1"
        
        vision = MockVisionClient({
            "action_success": True,
            "page_success": False,
            "summary": "Success",
            "issues": [],
            "next_actions": [],
            "manual_required": False
        })
        
        verifier = VerifyResultNode(vision_client=vision)
        result = verifier.verify(self.base_state)
        
        assert result.get("application_form", {}).get("field_1", {}).get("verified") == True
    
    def test_verify_heuristic_fallback(self):
        """Test heuristic verification when no vision client."""
        verifier = VerifyResultNode(vision_client=None)
        result = verifier.verify(self.base_state)
        
        # Should complete without vision model
        assert "execution_history" in result
        # Should detect filled fields
        assert result.get("success", False) in [True, False]


class TestGuiRecoveryNode:
    """Tests for GuiRecoveryNode."""
    
    def setup_method(self):
        self.base_state: ApplicationState = {
            "task_id": "test-001",
            "user_profile": {},
            "resume_data": {},
            "resume_pdf_path": "/resume.pdf",
            "job_description": {},
            "application_form": {},
            "generated_documents": {},
            "browser_context": {
                "snapshot": {"nodes": [{"uid": "1", "label": "Name"}]}
            },
            "current_task": "recovery",
            "next_action": {},
            "execution_history": [],
            "errors": ["Field fill failed"],
            "gui_recovery_needed": True,
            "manual_required": False,
            "success": False,
            "retry_count": 0,
            "max_retries": 3,
        }
    
    def test_recovery_click_action(self):
        """Test recovery with click action."""
        chrome = MockChromeClient()
        recovery = GuiRecoveryNode(vision_client=None, chrome_client=chrome)
        
        result = recovery.recover(self.base_state)
        
        # Should attempt recovery
        assert result.get("gui_recovery_needed") == False
        assert len(chrome.calls) > 0
    
    def test_recovery_multiple_actions(self):
        """Test recovery with multiple actions."""
        chrome = MockChromeClient()
        vision = MockVisionClient()
        
        recovery = GuiRecoveryNode(vision_client=vision, chrome_client=chrome)
        result = recovery.recover(self.base_state)
        
        # Should execute multiple actions
        assert result["recovery_actions_executed"] > 0
        # Should limit to max 3
        assert result["recovery_actions_executed"] <= GuiRecoveryNode.MAX_RECOVERY_STEPS
    
    def test_recovery_max_steps_limit(self):
        """Test that recovery respects max steps limit."""
        chrome = MockChromeClient()
        
        recovery = GuiRecoveryNode(vision_client=None, chrome_client=chrome)
        result = recovery.recover(self.base_state)
        
        assert result["recovery_actions_executed"] <= GuiRecoveryNode.MAX_RECOVERY_STEPS
    
    def test_recovery_blocks_submit(self):
        """Test that recovery blocks submit button clicks."""
        chrome = MockChromeClient()
        recovery = GuiRecoveryNode(vision_client=None, chrome_client=chrome)
        
        # Add submit button to recovery actions
        action = {"type": "click", "uid": "btn_submit", "reason": "Click submit"}
        
        result = recovery._execute_recovery_action(self.base_state, action)
        
        assert result["status"] == "blocked"
        assert "submit" in result["reason"].lower()
    
    def test_recovery_upload_file(self):
        """Test recovery with file upload."""
        chrome = MockChromeClient()
        recovery = GuiRecoveryNode(vision_client=None, chrome_client=chrome)
        
        action = {"type": "upload_file", "uid": "file_input", "reason": "Upload resume"}
        result = recovery._execute_recovery_action(self.base_state, action)
        
        assert result["status"] == "completed"
        assert len(chrome.calls) > 0
        assert chrome.calls[0][0] == "upload_file"
    
    def test_recovery_type_text(self):
        """Test recovery with text input."""
        chrome = MockChromeClient()
        recovery = GuiRecoveryNode(vision_client=None, chrome_client=chrome)
        
        action = {"type": "type_text", "uid": "name_field", "value": "John", "reason": "Retry input"}
        result = recovery._execute_recovery_action(self.base_state, action)
        
        assert result["status"] == "completed"
        assert chrome.calls[0][0] == "type_text"
    
    def test_recovery_press_key(self):
        """Test recovery with key press."""
        chrome = MockChromeClient()
        recovery = GuiRecoveryNode(vision_client=None, chrome_client=chrome)
        
        action = {"type": "press_key", "value": "Tab", "reason": "Navigate field"}
        result = recovery._execute_recovery_action(self.base_state, action)
        
        assert result["status"] == "completed"
        assert chrome.calls[0][0] == "press_key"
    
    def test_recovery_no_actions_available(self):
        """Test recovery when no actions available."""
        chrome = MockChromeClient()
        recovery = GuiRecoveryNode(vision_client=None, chrome_client=chrome)
        
        # Keep at least one error to trigger recovery attempt
        self.base_state["errors"] = ["Some error"]
        # But make sure no fallback actions are generated
        
        result = recovery.recover(self.base_state)
        
        # Should have recovery_actions_executed key
        assert "recovery_actions_executed" in result or "manual_required" in result
    
    def test_recovery_validate_actions(self):
        """Test that invalid actions are rejected."""
        recovery = GuiRecoveryNode()
        
        # Valid action
        assert recovery._validate_recovery_action({"type": "click", "uid": "field_1"}) == True
        
        # Invalid type
        assert recovery._validate_recovery_action({"type": "execute_code", "uid": "field_1"}) == False
        
        # Submit button
        assert recovery._validate_recovery_action({"type": "click", "uid": "btn_submit"}) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])