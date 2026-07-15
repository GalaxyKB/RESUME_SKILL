"""In-memory task state storage for workflow."""

import uuid
import time
from typing import Dict, Any, Optional, List
from threading import Lock
from .state import ApplicationState


class TaskStore:
    """In-memory task state store."""
    
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_logs: Dict[str, List[Dict[str, Any]]] = {}
        self.lock = Lock()
    
    def create_task(self, initial_state: Dict[str, Any]) -> str:
        """Create a new task with initial state.
        
        Args:
            initial_state: Initial state dictionary
            
        Returns:
            Task ID string
        """
        with self.lock:
            task_id = str(uuid.uuid4())
            
            # Create task with metadata
            task = {
                "task_id": task_id,
                "state": {
                    "task_id": task_id,
                    "user_profile": initial_state.get("user_profile", {}),
                    "resume_data": initial_state.get("resume_data", {}),
                    "resume_pdf_path": initial_state.get("resume_pdf_path", ""),
                    "job_description": initial_state.get("job_description", {}),
                    "application_form": initial_state.get("application_form", {}),
                    "generated_documents": initial_state.get("generated_documents", {}),
                    "browser_context": initial_state.get("browser_context", {}),
                    "current_task": initial_state.get("current_task", "application_planning"),
                    "next_action": initial_state.get("next_action", ""),
                    "execution_history": initial_state.get("execution_history", []),
                    "errors": initial_state.get("errors", []),
                    "gui_recovery_needed": initial_state.get("gui_recovery_needed", False),
                    "manual_required": initial_state.get("manual_required", False),
                    "success": initial_state.get("success", False),
                    "retry_count": initial_state.get("retry_count", 0),
                    "max_retries": initial_state.get("max_retries", 3),
                },
                "created_at": time.time(),
                "updated_at": time.time(),
                "status": "created",
            }
            
            self.tasks[task_id] = task
            self.task_logs[task_id] = []
            
            print(f"[TaskStore] Created task {task_id}")
            return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID.
        
        Args:
            task_id: Task ID string
            
        Returns:
            Task dictionary or None if not found
        """
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                # Return a copy to prevent external modification
                return task.copy()
            return None
    
    def update_task(self, task_id: str, patch: Dict[str, Any]) -> bool:
        """Update task state.
        
        Args:
            task_id: Task ID string
            patch: Partial state to update
            
        Returns:
            True if updated, False if task not found
        """
        with self.lock:
            if task_id not in self.tasks:
                print(f"[TaskStore] Task {task_id} not found for update")
                return False
            
            task = self.tasks[task_id]
            
            # Update state
            if "state" in patch:
                task["state"].update(patch["state"])
            
            # Update metadata
            task["updated_at"] = time.time()
            
            # Update status if provided
            if "status" in patch:
                task["status"] = patch["status"]
            
            print(f"[TaskStore] Updated task {task_id}")
            return True
    
    def append_log(self, task_id: str, message: str, level: str = "info", 
                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Append log message to task.
        
        Args:
            task_id: Task ID string
            message: Log message
            level: Log level (info, warning, error, debug)
            metadata: Additional metadata
            
        Returns:
            True if logged, False if task not found
        """
        with self.lock:
            if task_id not in self.task_logs:
                print(f"[TaskStore] Task {task_id} not found for logging")
                return False
            
            log_entry = {
                "timestamp": time.time(),
                "level": level,
                "message": message,
                "metadata": metadata or {}
            }
            
            self.task_logs[task_id].append(log_entry)
            
            # Also update execution history in task state
            if task_id in self.tasks:
                self.tasks[task_id]["state"]["execution_history"] = self.tasks[task_id]["state"].get("execution_history", []) + [
                    {"step": "log", "status": level, "message": message, "metadata": metadata or {}}
                ]
            
            print(f"[TaskStore] [{level.upper()}] {message} (task: {task_id})")
            return True
    
    def get_task_logs(self, task_id: str, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
        """Get task logs.
        
        Args:
            task_id: Task ID string
            limit: Maximum number of logs to return
            
        Returns:
            List of log entries or None if task not found
        """
        with self.lock:
            if task_id not in self.task_logs:
                return None
            
            logs = self.task_logs[task_id]
            if limit:
                return logs[-limit:]
            return logs.copy()
    
    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all tasks, optionally filtered by status.
        
        Args:
            status: Filter by task status
            
        Returns:
            List of task summaries
        """
        with self.lock:
            tasks = []
            for task_id, task in self.tasks.items():
                if status is None or task.get("status") == status:
                    tasks.append({
                        "task_id": task_id,
                        "status": task.get("status"),
                        "created_at": task.get("created_at"),
                        "updated_at": task.get("updated_at"),
                        "success": task["state"].get("success", False),
                        "current_task": task["state"].get("current_task", ""),
                        "error_count": len(task["state"].get("errors", [])),
                    })
            
            return sorted(tasks, key=lambda x: x["created_at"], reverse=True)
    
    def delete_task(self, task_id: str) -> bool:
        """Delete task and its logs.
        
        Args:
            task_id: Task ID string
            
        Returns:
            True if deleted, False if not found
        """
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
            
            if task_id in self.task_logs:
                del self.task_logs[task_id]
            
            print(f"[TaskStore] Deleted task {task_id}")
            return True
    
    def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """Clean up old tasks.
        
        Args:
            max_age_seconds: Maximum age in seconds
        """
        with self.lock:
            current_time = time.time()
            to_delete = []
            
            for task_id, task in self.tasks.items():
                if current_time - task.get("updated_at", 0) > max_age_seconds:
                    to_delete.append(task_id)
            
            for task_id in to_delete:
                self.delete_task(task_id)
            
            if to_delete:
                print(f"[TaskStore] Cleaned up {len(to_delete)} old tasks")


# Global task store instance
_task_store = TaskStore()


def create_task(initial_state: Dict[str, Any]) -> str:
    """Create a new task.
    
    Args:
        initial_state: Initial state dictionary
        
    Returns:
        Task ID string
    """
    return _task_store.create_task(initial_state)


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Get task by ID.
    
    Args:
        task_id: Task ID string
        
    Returns:
        Task dictionary or None if not found
    """
    return _task_store.get_task(task_id)


def update_task(task_id: str, patch: Dict[str, Any]) -> bool:
    """Update task state.
    
    Args:
        task_id: Task ID string
        patch: Partial state to update
        
    Returns:
        True if updated, False if task not found
    """
    return _task_store.update_task(task_id, patch)


def append_log(task_id: str, message: str, level: str = "info", 
              metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Append log message to task.
    
    Args:
        task_id: Task ID string
        message: Log message
        level: Log level (info, warning, error, debug)
        metadata: Additional metadata
        
    Returns:
        True if logged, False if task not found
    """
    return _task_store.append_log(task_id, message, level, metadata)


def get_task_logs(task_id: str, limit: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
    """Get task logs.
    
    Args:
        task_id: Task ID string
        limit: Maximum number of logs to return
        
    Returns:
        List of log entries or None if task not found
    """
    return _task_store.get_task_logs(task_id, limit)


def list_tasks(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all tasks.
    
    Args:
        status: Filter by task status
        
    Returns:
        List of task summaries
    """
    return _task_store.list_tasks(status)