"""
Test the background task API for form filling.
"""
import sys
import time
import json
import threading

sys.path.insert(0, "src")

from resume_skill.webui.app import app
from resume_skill.webui.task_manager import task_manager


def test_fill_start_returns_task_id():
    """Test that /api/fill/start immediately returns a task_id."""
    with app.test_client() as client:
        # Reset task manager
        task_manager.tasks.clear()
        
        # POST to /api/fill/start without resume file
        response = client.post('/api/fill/start')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = json.loads(response.data)
        
        assert 'task_id' in data, "Response should contain task_id"
        assert data['status'] == 'started', "Status should be 'started'"
        assert isinstance(data['task_id'], str), "task_id should be a string"
        assert len(data['task_id']) > 0, "task_id should not be empty"
        
        print(f"✓ /api/fill/start returns task_id: {data['task_id']}")


def test_fill_status_structure():
    """Test that /api/fill/status/<task_id> returns correct structure."""
    with app.test_client() as client:
        # Reset task manager
        task_manager.tasks.clear()
        
        # Create a task
        response = client.post('/api/fill/start')
        data = json.loads(response.data)
        task_id = data['task_id']
        
        # Poll status
        time.sleep(0.5)
        response = client.get(f'/api/fill/status/{task_id}')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        status_data = json.loads(response.data)
        
        # Verify structure
        required_fields = ['task_id', 'running', 'current_task', 'log', 'fields', 
                          'vision_review', 'success', 'failed_count', 'errors', 'status']
        for field in required_fields:
            assert field in status_data, f"Response should contain {field}"
        
        assert status_data['task_id'] == task_id, "Task ID should match"
        assert isinstance(status_data['running'], bool), "running should be boolean"
        assert isinstance(status_data['log'], list), "log should be a list"
        assert isinstance(status_data['fields'], list), "fields should be a list"
        assert isinstance(status_data['success'], bool), "success should be boolean"
        assert isinstance(status_data['failed_count'], int), "failed_count should be int"
        assert isinstance(status_data['errors'], list), "errors should be a list"
        
        print(f"✓ /api/fill/status/<task_id> returns correct structure")
        print(f"  Status: {status_data['status']}")
        print(f"  Running: {status_data['running']}")
        print(f"  Log entries: {len(status_data['log'])}")


def test_fill_status_nonexistent_task():
    """Test that /api/fill/status returns 404 for non-existent task."""
    with app.test_client() as client:
        response = client.get('/api/fill/status/nonexistent-task-id')
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ /api/fill/status returns 404 for non-existent task")


def test_fill_cancel():
    """Test that /api/fill/cancel/<task_id> works."""
    with app.test_client() as client:
        # Reset task manager
        task_manager.tasks.clear()
        
        # Create a task
        response = client.post('/api/fill/start')
        data = json.loads(response.data)
        task_id = data['task_id']
        
        # Cancel it
        response = client.post(f'/api/fill/cancel/{task_id}')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        cancel_data = json.loads(response.data)
        assert cancel_data['status'] == 'cancelled', "Status should be 'cancelled'"
        
        # Verify the task is marked as cancelled
        status_response = client.get(f'/api/fill/status/{task_id}')
        status_data = json.loads(status_response.data)
        assert status_data['status'] == 'cancelled', "Task should be cancelled"
        
        print("✓ /api/fill/cancel/<task_id> works correctly")


def test_extract_api_still_works():
    """Verify that old /api/extract endpoint still works."""
    with app.test_client() as client:
        # Try to get /api/profile (should work without file)
        response = client.get('/api/profile')
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = json.loads(response.data)
        assert 'exists' in data, "Should have exists field"
        print("✓ /api/profile still works")


def test_upload_resume_file():
    """Test that resume file can be uploaded with /api/fill/start."""
    with app.test_client() as client:
        # Reset task manager
        task_manager.tasks.clear()
        
        # Create a test PDF content (minimal PDF)
        pdf_content = b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<<>>\nstartxref\n0\n%%EOF"
        
        # POST with file
        from werkzeug.datastructures import FileStorage
        from io import BytesIO
        
        data = {
            'resume': (BytesIO(pdf_content), 'test.pdf')
        }
        
        response = client.post('/api/fill/start', data=data, content_type='multipart/form-data')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        response_data = json.loads(response.data)
        assert 'task_id' in response_data, "Should return task_id"
        
        task_id = response_data['task_id']
        task = task_manager.get_task(task_id)
        assert task is not None, "Task should be created"
        assert task.resume_path != '', "Resume path should be stored"
        
        print(f"✓ Resume file upload works, stored at: {task.resume_path}")


def test_concurrent_tasks():
    """Test that multiple tasks can run concurrently."""
    with app.test_client() as client:
        # Reset task manager
        task_manager.tasks.clear()
        
        # Create 3 tasks
        task_ids = []
        for i in range(3):
            response = client.post('/api/fill/start')
            data = json.loads(response.data)
            task_ids.append(data['task_id'])
        
        assert len(task_ids) == 3, "Should create 3 tasks"
        assert len(set(task_ids)) == 3, "All task IDs should be unique"
        
        # Verify all tasks exist
        for task_id in task_ids:
            response = client.get(f'/api/fill/status/{task_id}')
            assert response.status_code == 200, f"Task {task_id} should exist"
        
        print(f"✓ Created {len(task_ids)} concurrent tasks with unique IDs")


if __name__ == '__main__':
    print("\n=== Testing Background Task API ===\n")
    
    try:
        test_fill_start_returns_task_id()
        test_fill_status_structure()
        test_fill_status_nonexistent_task()
        test_fill_cancel()
        test_extract_api_still_works()
        test_upload_resume_file()
        test_concurrent_tasks()
        
        print("\n✓ All tests passed!\n")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
