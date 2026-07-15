"""Background task management used by the Web UI.

This module supports two compatible APIs:
- FillTask: the WebUI fill workflow status object used by /api/fill/*.
- BackgroundTask: a generic threaded task API used by workflow tests and future jobs.
"""

from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FillTask:
    task_id: str
    resume_path: str = ""
    status: str = TaskStatus.PENDING.value
    current_task: str = ""
    log: list[str] = field(default_factory=list)
    fields: list[dict[str, Any]] = field(default_factory=list)
    vision_review: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    failed_count: int = 0
    errors: list[str] = field(default_factory=list)
    execution_history: list[dict[str, Any]] = field(default_factory=list)
    manual_required: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    thread: Optional[threading.Thread] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "running": self.status in {TaskStatus.PENDING.value, TaskStatus.RUNNING.value},
            "current_task": self.current_task,
            "log": self.log[-20:],
            "fields": self.fields,
            "vision_review": self.vision_review,
            "success": self.success,
            "failed_count": self.failed_count,
            "errors": self.errors,
            "execution_history": self.execution_history[-20:],
            "manual_required": self.manual_required,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def add_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{timestamp}] {message}")


@dataclass
class BackgroundTask:
    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    current_step: str = ""
    total_steps: int = 0
    result: Any = None
    errors: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    thread: Optional[threading.Thread] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "progress": self.progress,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "result": self.result,
            "errors": self.errors,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class TaskManager:
    def __init__(self) -> None:
        self.tasks: Dict[str, FillTask | BackgroundTask] = {}
        self.lock = threading.RLock()

    def create_task(self, name_or_resume_path: str = "", func: Callable[..., Any] | None = None, *args: Any, **kwargs: Any):
        """Create either a FillTask or a generic BackgroundTask.

        WebUI fill API calls create_task(resume_path) and expects a FillTask.
        Generic tests call create_task(name, func, *args, **kwargs) and expect a task_id.
        """
        if callable(func):
            return self._create_background_task(name_or_resume_path, func, *args, **kwargs)

        task_id = str(uuid.uuid4())[:8]
        task = FillTask(task_id=task_id, resume_path=name_or_resume_path or "")
        with self.lock:
            self.tasks[task_id] = task
        return task

    def _create_background_task(self, name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        task_id = str(uuid.uuid4())
        task = BackgroundTask(task_id=task_id, name=name)
        with self.lock:
            self.tasks[task_id] = task

        def runner() -> None:
            with self.lock:
                if task.status == TaskStatus.CANCELLED:
                    return
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now()
            try:
                result = func(*args, **kwargs)
                with self.lock:
                    if task.status != TaskStatus.CANCELLED:
                        task.result = result
                        task.progress = 100
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = datetime.now()
            except Exception as exc:
                with self.lock:
                    task.status = TaskStatus.FAILED
                    task.errors.append(str(exc))
                    task.errors.append(traceback.format_exc())
                    task.completed_at = datetime.now()

        thread = threading.Thread(target=runner, daemon=True)
        task.thread = thread
        thread.start()
        return task_id

    def get_task(self, task_id: str) -> Optional[FillTask]:
        with self.lock:
            task = self.tasks.get(task_id)
        return task if isinstance(task, FillTask) else None

    def get_task_status(self, task_id: str) -> Optional[BackgroundTask]:
        with self.lock:
            task = self.tasks.get(task_id)
        return task if isinstance(task, BackgroundTask) else None

    def update_task_progress(self, task_id: str, progress: int, current_step: str = "", total_steps: int = 0) -> bool:
        with self.lock:
            task = self.tasks.get(task_id)
            if not isinstance(task, BackgroundTask):
                return False
            task.progress = max(0, min(100, int(progress)))
            task.current_step = current_step
            task.total_steps = total_steps
            return True

    def cancel_task(self, task_id: str) -> bool:
        with self.lock:
            task = self.tasks.get(task_id)
            if isinstance(task, FillTask) and task.status != TaskStatus.CANCELLED.value:
                task.status = TaskStatus.CANCELLED.value
                task.add_log("任务已被取消")
                task.completed_at = task.completed_at or datetime.now()
                return True
            if isinstance(task, BackgroundTask) and task.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                return True
        return False

    def list_tasks(self, status: TaskStatus | str | None = None) -> list[BackgroundTask | FillTask]:
        with self.lock:
            tasks = list(self.tasks.values())
        if status is None:
            return tasks
        status_value = status.value if isinstance(status, TaskStatus) else str(status)
        return [task for task in tasks if (task.status.value if isinstance(task.status, TaskStatus) else task.status) == status_value]

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> None:
        cutoff_time = time.time() - (max_age_hours * 3600)
        with self.lock:
            to_remove = []
            for task_id, task in self.tasks.items():
                completed_at = getattr(task, "completed_at", None)
                created_at = getattr(task, "created_at", None)
                status = task.status.value if isinstance(task.status, TaskStatus) else task.status
                if completed_at and completed_at.timestamp() < cutoff_time:
                    to_remove.append(task_id)
                elif status in {"completed", "cancelled", "failed"} and created_at and created_at.timestamp() < cutoff_time:
                    to_remove.append(task_id)
            for task_id in to_remove:
                del self.tasks[task_id]


task_manager = TaskManager()


def get_task_manager() -> TaskManager:
    return task_manager


def create_background_task(name: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    return task_manager.create_task(name, func, *args, **kwargs)


def poll_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    task = task_manager.get_task_status(task_id)
    return task.to_dict() if task else None
