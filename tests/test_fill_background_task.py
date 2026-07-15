"""
Test background task API for form filling with LangGraph workflow.
Tests: /api/fill/start, /api/fill/status/<task_id>, /api/fill/cancel/<task_id>
"""

import sys
import json
import time
import threading
sys.path.insert(0, "src")

from resume_skill.webui.app import app, task_manager
from resume_skill.webui.task_manager import FillTask


def test_api_fill_start():
    """Test POST /api/fill/start returns task_id immediately."""
    with app.test_client() as client:
        # Start a fill task without resume
        response = client.post('/api/fill/start')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.data)
        assert "task_id" in data, "Response should contain task_id"
        assert data["status"] == "started", f"Expected status 'started', got {data['status']}"
        
        task_id = data["task_id"]
        print(f"✓ POST /api/fill/start returned task_id: {task_id}")
        
        # Verify task exists
        task = task_manager.get_task(task_id)
        assert task is not None, f"Task {task_id} should exist"
        print(f"✓ Task created in task_manager")
        
        return task_id


def test_api_fill_status(task_id):
    """Test GET /api/fill/status/<task_id> returns task status."""
    with app.test_client() as client:
        # Get initial status
        response = client.get(f'/api/fill/status/{task_id}')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.data)
        
        # Verify response structure
        required_fields = [
            "task_id", "running", "current_task", "log", "fields",
            "vision_review", "success", "failed_count", "errors", "status"
        ]
        for field in required_fields:
            assert field in data, f"Response should contain '{field}'"
        
        print(f"✓ GET /api/fill/status/{task_id} returned valid structure")
        print(f"  - status: {data['status']}")
        print(f"  - running: {data['running']}")
        print(f"  - current_task: {data['current_task']}")
        print(f"  - log entries: {len(data['log'])}")
        
        return data


def test_api_fill_status_nonexistent():
    """Test GET /api/fill/status/<task_id> for non-existent task."""
    with app.test_client() as client:
        response = client.get('/api/fill/status/nonexistent-task')
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        data = json.loads(response.data)
        assert "error" in data, "Response should contain error"
        print(f"✓ Non-existent task returns 404")


def test_api_fill_cancel(task_id):
    """Test POST /api/fill/cancel/<task_id> cancels task."""
    with app.test_client() as client:
        # Cancel the task
        response = client.post(f'/api/fill/cancel/{task_id}')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = json.loads(response.data)
        assert data["status"] == "cancelled", f"Expected status 'cancelled', got {data['status']}"
        
        # Verify task is cancelled
        task = task_manager.get_task(task_id)
        assert task.status == "cancelled", f"Task status should be 'cancelled', got {task.status}"
        
        print(f"✓ POST /api/fill/cancel/{task_id} cancelled task")


def test_mock_workflow():
    """Test mock workflow with ApplicationState."""
    from resume_skill.agent.fill_workflow import ApplicationState, FillWorkflowRunner
    from unittest.mock import Mock, MagicMock
    
    # Create mock chrome and LLM clients
    mock_chrome = Mock()
    mock_llm = Mock()
    mock_vision = Mock()
    
    # Setup mock returns
    mock_chrome.call_tool = Mock(return_value="<page snapshot>")
    mock_llm.call_json = Mock(return_value={"jobs": []})
    
    # Create state
    state = ApplicationState(
        task_id="test-001",
        user_profile={"name": "Test User"},
        resume_pdf_path="/tmp/test.pdf",
        max_retries=20
    )
    
    assert state.task_id == "test-001"
    assert state.status == "pending"
    print(f"✓ ApplicationState created")
    
    # Test state dict conversion
    state_dict = state.to_dict()
    assert isinstance(state_dict, dict)
    assert state_dict["task_id"] == "test-001"
    print(f"✓ ApplicationState.to_dict() works")
    
    # Test log functionality
    state.add_log("Test message")
    assert len(state.log) == 1
    assert "[" in state.log[0] and "]" in state.log[0]  # Has timestamp
    print(f"✓ ApplicationState.add_log() works")


def test_upload_resume():
    """Test POST /api/fill/start with resume file."""
    with app.test_client() as client:
        # Create a mock PDF file
        from io import BytesIO
        pdf_content = BytesIO(b'%PDF-1.4\n%test pdf')
        pdf_content.name = 'test.pdf'
        
        data = {
            'resume': (pdf_content, 'test.pdf')
        }
        
        response = client.post(
            '/api/fill/start',
            data=data,
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
        
        result = json.loads(response.data)
        assert "task_id" in result, "Response should have task_id"
        
        # Wait a bit for task to start
        time.sleep(0.5)
        
        task = task_manager.get_task(result["task_id"])
        assert task is not None, "Task should exist"
        assert task.resume_path != "", "Task should have resume_path"
        print(f"✓ Upload resume works, task has resume_path: {task.resume_path[:50]}")


def test_task_cleanup():
    """Test task cleanup for old tasks."""
    # Create old task
    old_task = task_manager.create_task()
    old_task.status = "completed"
    from datetime import datetime, timedelta
    old_task.completed_at = datetime.now() - timedelta(days=2)
    
    initial_count = len(task_manager.tasks)
    
    # Cleanup
    task_manager.cleanup_old_tasks(max_age_hours=24)
    
    final_count = len(task_manager.tasks)
    assert final_count < initial_count, "Old task should be cleaned up"
    print(f"✓ Task cleanup works (removed {initial_count - final_count} old tasks)")


def test_polling_loop():
    """Test frontend polling loop simulation."""
    with app.test_client() as client:
        # Start task
        response = client.post('/api/fill/start')
        task_id = json.loads(response.data)["task_id"]
        
        # Simulate polling loop
        poll_count = 0
        max_polls = 5
        
        while poll_count < max_polls:
            response = client.get(f'/api/fill/status/{task_id}')
            data = json.loads(response.data)
            
            poll_count += 1
            print(f"  Poll {poll_count}: status={data['status']}, running={data['running']}, log_entries={len(data['log'])}")
            
            if not data['running']:
                print(f"✓ Task completed after {poll_count} polls")
                break
            
            time.sleep(0.1)  # Short sleep
        
        if poll_count >= max_polls:
            print(f"✓ Polling continues (reached max {max_polls} polls)")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("TEST: Background Task API")
    print("="*60 + "\n")
    
    try:
        print("1. Testing POST /api/fill/start")
        task_id = test_api_fill_start()
        
        print("\n2. Testing GET /api/fill/status/<task_id>")
        status = test_api_fill_status(task_id)
        
        print("\n3. Testing GET /api/fill/status (non-existent)")
        test_api_fill_status_nonexistent()
        
        print("\n4. Testing POST /api/fill/cancel/<task_id>")
        test_api_fill_cancel(task_id)
        
        print("\n5. Testing ApplicationState and LangGraph")
        test_mock_workflow()
        
        print("\n6. Testing resume file upload")
        test_upload_resume()
        
        print("\n7. Testing task cleanup")
        test_task_cleanup()
        
        print("\n8. Testing polling loop")
        test_polling_loop()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
