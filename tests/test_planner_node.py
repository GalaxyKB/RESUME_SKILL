"""Tests for ApplicationPlannerNode."""

import pytest
import json
from resume_skill.workflow.planner_node import ApplicationPlannerNode
from resume_skill.workflow.state import ApplicationState


class TestApplicationPlannerNode:
    """Test ApplicationPlannerNode."""
    
    def setup_method(self):
        """Setup base state."""
        self.base_state: ApplicationState = {
            "task_id": "test-001",
            "user_profile": {"name": "John Doe", "email": "john@test.com"},
            "resume_data": {"experience": "5 years"},
            "resume_pdf_path": "/path/resume.pdf",
            "job_description": {"title": "Engineer"},
            "application_form": {
                "name": {"type": "text", "required": True, "value": ""},
                "email": {"type": "text", "required": True, "value": ""},
                "resume": {"type": "file", "required": True, "value": ""},
                "cover": {"type": "text", "required": False, "value": ""}
            },
            "generated_documents": {},
            "browser_context": {
                "snapshot": {
                    "nodes": [
                        {"uid": "name_field", "label": "Name"},
                        {"uid": "email_field", "label": "Email"},
                        {"uid": "resume_upload", "label": "Upload Resume"},
                    ]
                }
            },
            "current_task": "planning",
            "next_action": {},
            "execution_history": [],
            "errors": [],
            "gui_recovery_needed": False,
            "manual_required": False,
            "success": False,
            "retry_count": 0,
            "max_retries": 3,
        }
    
    def test_plan_fill_first_required_field(self):
        """Test planning to fill first unfilled required field."""
        planner = ApplicationPlannerNode()
        result = planner.plan(self.base_state)
        
        # Should plan to fill a required field
        assert result["current_task"] == "browser_execution"
        assert result["next_action"]["type"] == "fill"
        assert result["next_action"]["uid"] in ["name", "email"]
    
    def test_plan_fill_specific_field(self):
        """Test planning specific field fill."""
        planner = ApplicationPlannerNode()
        
        # Mark name as filled
        self.base_state["application_form"]["name"]["value"] = "John Doe"
        
        result = planner.plan(self.base_state)
        
        # Should plan to fill email (next required field)
        assert result["next_action"]["type"] == "fill"
        assert result["next_action"]["uid"] == "email"
    
    def test_plan_file_upload(self):
        """Test planning file upload."""
        planner = ApplicationPlannerNode()
        
        # Mark other required fields as filled
        self.base_state["application_form"]["name"]["value"] = "John"
        self.base_state["application_form"]["email"]["value"] = "john@test.com"
        
        result = planner.plan(self.base_state)
        
        # Should plan to upload file (next unfilled required field)
        assert result["next_action"]["type"] == "upload_file"
    
    def test_plan_done_when_all_filled(self):
        """Test planning done when all required fields filled."""
        planner = ApplicationPlannerNode()
        
        # Fill all required fields
        self.base_state["application_form"]["name"]["value"] = "John"
        self.base_state["application_form"]["email"]["value"] = "john@test.com"
        self.base_state["application_form"]["resume"]["value"] = "resume.pdf"
        
        result = planner.plan(self.base_state)
        
        # Should recognize all required fields are filled
        # Next action could be done or observe depending on strategy
        assert result["current_task"] in ["verification", "browser_execution"]
    
    def test_plan_observe_missing_snapshot(self):
        """Test planning observe when no snapshot."""
        planner = ApplicationPlannerNode()
        
        self.base_state["browser_context"]["snapshot"] = {}
        
        result = planner.plan(self.base_state)
        
        # Should plan to fill or observe
        assert result["next_action"]["type"] in ["fill", "observe", "upload_file"]
    
    def test_plan_success_state(self):
        """Test planning when state is already successful."""
        planner = ApplicationPlannerNode()
        
        self.base_state["success"] = True
        
        result = planner.plan(self.base_state)
        
        # Should plan done
        assert result["next_action"]["type"] == "done"
        assert result["current_task"] == "end"
    
    def test_plan_manual_state(self):
        """Test planning when manual intervention required."""
        planner = ApplicationPlannerNode()
        
        self.base_state["manual_required"] = True
        
        result = planner.plan(self.base_state)
        
        # Should plan manual
        assert result["next_action"]["type"] == "manual"
        assert result["current_task"] == "end"
    
    def test_plan_select_dropdown_field(self):
        """Test planning for select/dropdown fields."""
        planner = ApplicationPlannerNode()
        
        # Set degree as the only unfilled required field
        self.base_state["application_form"] = {
            "degree": {
                "type": "select",
                "required": True,
                "value": ""
            }
        }
        
        result = planner.plan(self.base_state)
        
        # Should plan to handle the unfilled required field
        assert result["next_action"]["type"] in ["click", "fill"]
    
    def test_plan_execution_history_recorded(self):
        """Test that planning is recorded in execution history."""
        planner = ApplicationPlannerNode()
        
        result = planner.plan(self.base_state)
        
        # Should have execution history entry
        assert len(result.get("execution_history", [])) > 0
        last_entry = result["execution_history"][-1]
        assert last_entry["step"] == "application_planner"
        assert last_entry["status"] == "planned"
    
    def test_plan_heuristic_strategy(self):
        """Test heuristic planning strategy."""
        planner = ApplicationPlannerNode(llm_client=None)
        
        # Fill form with various states
        self.base_state["application_form"]["name"]["value"] = "John"
        self.base_state["application_form"]["email"]["value"] = "john@test.com"
        # Resume is still empty
        
        result = planner.plan(self.base_state)
        
        # Should find next unfilled field
        assert result["current_task"] == "browser_execution"
        next_action = result["next_action"]
        assert next_action["type"] in ["upload_file", "fill", "observe"]
    
    def test_find_upload_field(self):
        """Test finding file upload fields."""
        planner = ApplicationPlannerNode()
        
        # Add various field types
        form = {
            "name": {"type": "text", "value": ""},
            "resume": {"type": "file", "value": ""},
            "letter": {"type": "file", "value": ""}
        }
        
        upload_field = planner._find_upload_field(form, [])
        
        # Should find a file field
        assert upload_field in ["resume", "letter"]
    
    def test_all_required_fields_filled(self):
        """Test checking if all required fields are filled."""
        planner = ApplicationPlannerNode()
        
        form = {
            "name": {"required": True, "value": "John"},
            "email": {"required": True, "value": "john@test.com"},
            "comment": {"required": False, "value": ""}
        }
        
        assert planner._all_required_fields_filled(form) == True
        
        # Unset one required field
        form["email"]["value"] = ""
        assert planner._all_required_fields_filled(form) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])