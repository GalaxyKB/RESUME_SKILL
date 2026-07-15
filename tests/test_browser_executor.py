"""Tests for BrowserExecutorNode."""

import pytest
from unittest.mock import Mock, MagicMock
from resume_skill.workflow.browser_executor import BrowserExecutorNode
from resume_skill.workflow.state import ApplicationState


class FakeChromeClient:
    """Mock Chrome DevTools client for testing."""
    
    def __init__(self):
        self.call_log = []
    
    def call_tool(self, name: str, params: dict) -> dict:
        """Record tool calls and return mock responses."""
        self.call_log.append({"tool": name, "params": params})
        
        if name == "take_snapshot":
            return {"nodes": [{"uid": "1", "label": "Test Form"}]}
        elif name == "take_screenshot":
            return {"data": "fake_image_data"}
        elif name == "fill":
            if params.get("value") == "error":
                raise RuntimeError("Fill failed")
            return {"success": True}
        elif name == "fill_form":
            return {"success": True, "filled": len(params.get("elements", []))}
        elif name == "click":
            if "error" in str(params.get("uid", "")):
                raise RuntimeError("Click failed")
            return {"success": True}
        elif name == "upload_file":
            return {"success": True, "file": params.get("filePath")}
        elif name == "type_text":
            return {"success": True}
        elif name == "press_key":
            return {"success": True}
        else:
            return {}


class TestBrowserExecutorNode:
    """Test BrowserExecutorNode actions."""
    
    def setup_method(self):
        """Setup for each test."""
        self.chrome = FakeChromeClient()
        self.executor = BrowserExecutorNode(chrome_client=self.chrome)
        self.base_state: ApplicationState = {
            "task_id": "test-001",
            "user_profile": {},
            "resume_data": {},
            "resume_pdf_path": "/path/to/resume.pdf",
            "job_description": {},
            "application_form": {},
            "generated_documents": {},
            "browser_context": {},
            "current_task": "browser_execution",
            "next_action": {},
            "execution_history": [],
            "errors": [],
            "gui_recovery_needed": False,
            "manual_required": False,
            "success": False,
            "retry_count": 0,
            "max_retries": 3,
        }
    
    def test_action_observe(self):
        """Test observe action captures snapshot and screenshot."""
        state = self.base_state.copy()
        state["next_action"] = {"type": "observe"}
        
        result = self.executor.execute(state)
        
        assert "browser_context" in result
        assert result["browser_context"].get("snapshot") is not None
        assert result["browser_context"].get("screenshot") is not None
        
        assert len(self.chrome.call_log) == 2
        assert self.chrome.call_log[0]["tool"] == "take_snapshot"
        assert self.chrome.call_log[1]["tool"] == "take_screenshot"
    
    def test_action_fill(self):
        """Test fill action."""
        state = self.base_state.copy()
        state["next_action"] = {
            "type": "fill",
            "uid": "field_1",
            "value": "test value"
        }
        
        result = self.executor.execute(state)
        
        assert len(result.get("execution_history", [])) > 0
        assert result["execution_history"][-1]["action_type"] == "fill"
        assert result["execution_history"][-1]["uid"] == "field_1"
        
        assert self.chrome.call_log[0]["tool"] == "fill"
        assert self.chrome.call_log[0]["params"]["uid"] == "field_1"
    
    def test_action_fill_missing_uid(self):
        """Test fill action with missing uid."""
        state = self.base_state.copy()
        state["next_action"] = {"type": "fill", "value": "test"}
        
        result = self.executor.execute(state)
        
        assert result["gui_recovery_needed"] == True
        assert len(result.get("errors", [])) > 0
        assert "missing uid" in result["errors"][0].lower()
    
    def test_action_fill_form(self):
        """Test fill_form action."""
        state = self.base_state.copy()
        elements = [
            {"uid": "1", "value": "John"},
            {"uid": "2", "value": "Doe"}
        ]
        state["next_action"] = {"type": "fill_form", "elements": elements}
        
        result = self.executor.execute(state)
        
        assert self.chrome.call_log[0]["tool"] == "fill_form"
        assert self.chrome.call_log[0]["params"]["elements"] == elements
    
    def test_action_click(self):
        """Test click action."""
        state = self.base_state.copy()
        state["next_action"] = {"type": "click", "uid": "btn_next"}
        
        result = self.executor.execute(state)
        
        assert self.chrome.call_log[0]["tool"] == "click"
        assert self.chrome.call_log[0]["params"]["uid"] == "btn_next"
    
    def test_action_click_forbidden_submit(self):
        """Test that forbidden submit buttons are not auto-clicked."""
        state = self.base_state.copy()
        state["next_action"] = {"type": "click", "uid": "btn_submit"}
        state["allow_submit"] = False
        
        result = self.executor.execute(state)
        
        # Should be blocked
        assert result["manual_required"] == True
        assert "blocked" in result["execution_history"][-1]["status"].lower()
        
        # Chrome client should not have been called
        assert len(self.chrome.call_log) == 0
    
    def test_action_click_submit_allowed(self):
        """Test that submit can be clicked when explicitly allowed."""
        state = self.base_state.copy()
        state["next_action"] = {"type": "click", "uid": "btn_submit"}
        state["allow_submit"] = True
        
        result = self.executor.execute(state)
        
        # Should succeed
        assert result.get("manual_required", False) == False
        assert len(self.chrome.call_log) == 1
        assert self.chrome.call_log[0]["tool"] == "click"
    
    def test_action_upload_file_with_path(self):
        """Test upload_file with explicit path."""
        state = self.base_state.copy()
        state["next_action"] = {
            "type": "upload_file",
            "uid": "file_input",
            "file_path": "/custom/path/resume.pdf"
        }
        
        result = self.executor.execute(state)
        
        assert self.chrome.call_log[0]["tool"] == "upload_file"
        assert self.chrome.call_log[0]["params"]["filePath"] == "/custom/path/resume.pdf"
    
    def test_action_upload_file_default_resume(self):
        """Test upload_file uses resume_pdf_path by default."""
        state = self.base_state.copy()
        state["resume_pdf_path"] = "/my/resume.pdf"
        state["next_action"] = {"type": "upload_file", "uid": "file_input"}
        
        result = self.executor.execute(state)
        
        assert self.chrome.call_log[0]["tool"] == "upload_file"
        assert self.chrome.call_log[0]["params"]["filePath"] == "/my/resume.pdf"
    
    def test_action_upload_file_missing_path(self):
        """Test upload_file with missing path."""
        state = self.base_state.copy()
        state["resume_pdf_path"] = ""
        state["next_action"] = {"type": "upload_file", "uid": "file_input"}
        
        result = self.executor.execute(state)
        
        assert result["gui_recovery_needed"] == True
        assert "missing" in result["errors"][0].lower()
    
    def test_action_type_text(self):
        """Test type_text action."""
        state = self.base_state.copy()
        state["next_action"] = {
            "type": "type_text",
            "uid": "search_box",
            "value": "search query"
        }
        
        result = self.executor.execute(state)
        
        assert self.chrome.call_log[0]["tool"] == "type_text"
    
    def test_action_press_key(self):
        """Test press_key action."""
        state = self.base_state.copy()
        state["next_action"] = {"type": "press_key", "value": "Enter"}
        
        result = self.executor.execute(state)
        
        assert self.chrome.call_log[0]["tool"] == "press_key"
        assert self.chrome.call_log[0]["params"]["key"] == "Enter"
    
    def test_action_wait(self):
        """Test wait action."""
        state = self.base_state.copy()
        state["next_action"] = {"type": "wait", "value": 0.1}
        
        result = self.executor.execute(state)
        
        assert len(result["execution_history"]) > 0
        assert result["execution_history"][-1]["action_type"] == "wait"
        # No Chrome client calls for wait
        assert len(self.chrome.call_log) == 0
    
    def test_action_manual(self):
        """Test manual intervention action."""
        state = self.base_state.copy()
        state["next_action"] = {
            "type": "manual",
            "reason": "User needs to enter CAPTCHA"
        }
        
        result = self.executor.execute(state)
        
        assert result["manual_required"] == True
        assert "manual_intervention" in result["execution_history"][-1]["status"]
    
    def test_action_done(self):
        """Test done action marks workflow complete."""
        state = self.base_state.copy()
        state["next_action"] = {"type": "done"}
        
        result = self.executor.execute(state)
        
        assert result["success"] == True
        assert result["execution_history"][-1]["action_type"] == "done"
    
    def test_execution_error_handling(self):
        """Test that errors trigger recovery mode."""
        state = self.base_state.copy()
        state["next_action"] = {
            "type": "fill",
            "uid": "field_error",
            "value": "error"  # Will trigger fake error
        }
        
        result = self.executor.execute(state)
        
        assert result["gui_recovery_needed"] == True
        assert len(result.get("errors", [])) > 0
        assert "failed" in result["errors"][0].lower()
    
    def test_forbidden_keywords(self):
        """Test all forbidden submit keywords."""
        forbidden_uids = [
            "btn_submit", "button_提交", "final_step",
            "click_apply", "投递按钮", "send_application"
        ]
        
        for uid in forbidden_uids:
            state = self.base_state.copy()
            state["next_action"] = {"type": "click", "uid": uid}
            state["allow_submit"] = False
            
            result = self.executor.execute(state)
            assert result["manual_required"] == True, f"Should block {uid}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])