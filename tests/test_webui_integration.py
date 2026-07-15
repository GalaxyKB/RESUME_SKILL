"""Test WebUI integration with LangGraph workflow."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime


def test_fill_task_logging():
    """Test FillTask logging functionality."""
    from resume_skill.webui.task_manager import FillTask
    
    task = FillTask("test-task-2")
    
    task.add_log("Test message 1")
    task.add_log("Test message 2")
    
    assert len(task.log) == 2
    assert "Test message 1" in task.log[0]
    assert "Test message 2" in task.log[1]


def test_flask_app_imports():
    """Test that Flask app can be imported."""
    from resume_skill.webui.app import app
    assert app is not None


def test_flask_app_has_routes():
    """Test that Flask app has expected routes."""
    from resume_skill.webui.app import app
    
    routes = [str(rule) for rule in app.url_map.iter_rules()]
    
    # Check for key endpoints
    assert any("/api/fill/start" in r for r in routes)
    assert any("/api/fill/status" in r for r in routes)
    assert any("/api/fill/cancel" in r for r in routes)
    assert any("/api/extract" in r for r in routes)
    assert any("/api/consolidate" in r for r in routes)


@patch('resume_skill.webui.app._get_or_start_chrome')
def test_execute_fill_task_structure(mock_chrome):
    """Test that _execute_fill_task function exists and has correct structure."""
    from resume_skill.webui.app import _execute_fill_task
    from resume_skill.webui.task_manager import FillTask
    import inspect
    
    # Check the function exists
    assert _execute_fill_task is not None
    
    # Check it takes a task parameter
    sig = inspect.signature(_execute_fill_task)
    params = list(sig.parameters.keys())
    assert "task" in params


def test_workflow_graph_buildable():
    """Test that LangGraph workflow can be built."""
    from resume_skill.workflow import build_application_graph
    
    graph = build_application_graph()
    assert graph is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
