"""Tests for background task workflow with polling."""

import pytest
import time
from resume_skill.webui.task_manager import (
    TaskManager,
    TaskStatus,
    create_background_task,
    poll_task_status,
    get_task_manager,
)


class TestTaskManager:
    """Test TaskManager functionality."""
    
    def test_create_and_poll_task(self):
        """Test creating a task and polling its status."""
        manager = TaskManager()
        
        def simple_task():
            time.sleep(0.1)
            return {"result": "completed"}
        
        # Create task
        task_id = manager.create_task("simple_task", simple_task)
        assert task_id is not None
        assert len(task_id) > 10
        
        # Poll immediately - should be running or pending
        status = manager.get_task_status(task_id)
        assert status is not None
        assert status.task_id == task_id
        assert status.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
        
        # Wait for completion
        time.sleep(0.5)
        status = manager.get_task_status(task_id)
        assert status.status == TaskStatus.COMPLETED
        assert status.progress == 100
        assert status.result == {"result": "completed"}
    
    def test_task_with_exception(self):
        """Test task that raises exception."""
        manager = TaskManager()
        
        def failing_task():
            raise ValueError("Test error")
        
        task_id = manager.create_task("failing_task", failing_task)
        
        # Wait for completion
        time.sleep(0.2)
        status = manager.get_task_status(task_id)
        
        assert status.status == TaskStatus.FAILED
        assert len(status.errors) > 0
        assert "Test error" in status.errors[0]
    
    def test_update_progress(self):
        """Test updating task progress."""
        manager = TaskManager()
        
        # We need to capture task_id in closure
        task_id_holder = {}
        
        def progress_task():
            task_id = task_id_holder.get("id")
            if task_id:
                # Update progress from within task
                manager.update_task_progress(task_id, 25, "Step 1", 4)
                time.sleep(0.05)
                manager.update_task_progress(task_id, 50, "Step 2", 4)
                time.sleep(0.05)
                manager.update_task_progress(task_id, 75, "Step 3", 4)
                time.sleep(0.05)
            return {"steps": 4}
        
        task_id = manager.create_task("progress_task", progress_task)
        task_id_holder["id"] = task_id
        
        # Check initial progress
        time.sleep(0.1)
        status = manager.get_task_status(task_id)
        assert status.progress >= 0
        
        # Wait for completion
        time.sleep(0.5)
        status = manager.get_task_status(task_id)
        assert status.status == TaskStatus.COMPLETED
    
    def test_cancel_task(self):
        """Test cancelling a task."""
        manager = TaskManager()
        
        def long_task():
            time.sleep(2)
            return {"result": "completed"}
        
        task_id = manager.create_task("long_task", long_task)
        
        # Cancel immediately
        cancelled = manager.cancel_task(task_id)
        assert cancelled == True
        
        status = manager.get_task_status(task_id)
        assert status.status == TaskStatus.CANCELLED
        
        # Cannot cancel already cancelled task
        cancelled = manager.cancel_task(task_id)
        assert cancelled == False
    
    def test_task_not_found(self):
        """Test handling of non-existent task."""
        manager = TaskManager()
        
        status = manager.get_task_status("non-existent-id")
        assert status is None
        
        updated = manager.update_task_progress("non-existent-id", 50, "step")
        assert updated == False
    
    def test_list_tasks(self):
        """Test listing tasks."""
        manager = TaskManager()
        
        # Create multiple tasks
        def dummy_task(i):
            return {"index": i}
        
        task_ids = []
        for i in range(3):
            task_id = manager.create_task(f"task_{i}", dummy_task, i)
            task_ids.append(task_id)
        
        # List all tasks immediately (may be pending or running)
        all_tasks = manager.list_tasks()
        assert len(all_tasks) >= 3
        
        # Wait for completion
        time.sleep(0.3)
        
        # List by status
        completed = manager.list_tasks(status=TaskStatus.COMPLETED)
        assert len(completed) >= 1


class TestBackgroundTaskAPI:
    """Test background task API functions."""
    
    def test_create_background_task_function(self):
        """Test create_background_task helper."""
        def sample_task(x, y):
            return x + y
        
        task_id = create_background_task("math_task", sample_task, 2, 3)
        assert task_id is not None
        
        # Wait for completion
        time.sleep(0.2)
        status = poll_task_status(task_id)
        
        assert status is not None
        assert status["status"] == TaskStatus.COMPLETED.value
        assert status["result"] == 5
    
    def test_poll_task_status_function(self):
        """Test poll_task_status helper."""
        def quick_task():
            return {"data": "test"}
        
        task_id = create_background_task("quick_task", quick_task)
        
        # Poll immediately
        status = poll_task_status(task_id)
        assert status is not None
        assert "task_id" in status
        assert "status" in status
        assert "progress" in status
        
        # Status should be JSON-serializable
        assert isinstance(status["status"], str)
        
        # Wait for completion
        time.sleep(0.2)
        status = poll_task_status(task_id)
        
        assert status["status"] == TaskStatus.COMPLETED.value
        assert status["result"] == {"data": "test"}
    
    def test_poll_non_existent_task(self):
        """Test polling non-existent task."""
        status = poll_task_status("non-existent-task-id")
        assert status is None
    
    def test_get_task_manager_singleton(self):
        """Test that get_task_manager returns same instance."""
        manager1 = get_task_manager()
        manager2 = get_task_manager()
        
        # Should be same instance
        assert manager1 is manager2


class TestLongRunningWorkflow:
    """Test long-running workflow scenario (avoiding fetch abort)."""
    
    def test_simulated_form_filling(self):
        """Simulate form filling with progress updates."""
        manager = TaskManager()
        
        def fill_form_task(task_id, form_data):
            """Simulate filling a form with multiple steps."""
            steps = [
                ("Initializing browser", 10),
                ("Navigating to form", 20),
                ("Filling personal info", 40),
                ("Filling education", 60),
                ("Filling experience", 80),
                ("Submitting form", 100),
            ]
            
            for step_name, progress in steps:
                manager.update_task_progress(task_id, progress, step_name, len(steps))
                time.sleep(0.05)  # Simulate step duration
            
            return {"form_id": form_data.get("id"), "status": "submitted"}
        
        form_data = {"id": "form_123", "fields": {}}
        task_id = manager.create_task("fill_form", fill_form_task, task_id="temp", form_data=form_data)
        
        # Simulate polling from client
        statuses = []
        for _ in range(10):
            status = manager.get_task_status(task_id)
            if status:
                statuses.append(status.progress)
            time.sleep(0.05)
        
        # Should have increasing progress
        assert len(statuses) > 0
        assert statuses[-1] == 100
        
        # Verify final result
        final_status = manager.get_task_status(task_id)
        assert final_status.status == TaskStatus.COMPLETED
        assert final_status.result["form_id"] == "form_123"
    
    def test_multiple_concurrent_tasks(self):
        """Test handling multiple concurrent tasks."""
        manager = TaskManager()
        
        def task_func(duration):
            time.sleep(duration)
            return {"duration": duration}
        
        # Create multiple concurrent tasks
        task_ids = []
        for i in range(5):
            task_id = manager.create_task(f"task_{i}", task_func, 0.1 * (i + 1))
            task_ids.append(task_id)
        
        # Poll all tasks
        all_tasks = manager.list_tasks()
        assert len(all_tasks) >= 5
        
        # Wait for all to complete
        time.sleep(1)
        
        completed_count = 0
        for task_id in task_ids:
            status = manager.get_task_status(task_id)
            if status.status == TaskStatus.COMPLETED:
                completed_count += 1
        
        assert completed_count == 5


if __name__ == "__main__":
    # Run tests manually
    print("Running task manager tests...")
    pytest.main([__file__, "-v"])