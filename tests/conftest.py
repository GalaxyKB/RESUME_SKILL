"""Pytest collection safeguards.

Several legacy smoke tests start Flask, Chrome DevTools MCP, or real HTTP calls at
module import time. Keep default pytest runs fast and offline; run those files
explicitly when doing manual integration verification.
"""

collect_ignore = [
    "../test_output.txt",
    "test_chrome_client.py",
    "test_chrome_client_v2.py",
    "test_chrome_full.py",
    "test_chrome_simple.py",
    "test_extract_api.py",
    "test_scout_flow.py",
    "test_webui.py",
]


def _fake_execute_fill_task(task):
    from datetime import datetime

    task.status = "completed"
    task.started_at = datetime.now()
    task.completed_at = datetime.now()
    task.current_task = "测试模式：跳过真实浏览器和模型调用"
    task.success = True
    task.failed_count = 0
    task.fields = []
    task.vision_review = {"ok": True, "summary": "测试模式通过", "issues": []}
    task.add_log("测试模式：任务已完成")


def pytest_configure(config):
    try:
        from resume_skill.webui import app as webapp

        webapp.app.config["TESTING"] = True
        webapp._execute_fill_task = _fake_execute_fill_task
    except Exception:
        pass


import pytest


@pytest.fixture
def task_id():
    from resume_skill.webui.app import app, task_manager

    with app.test_client() as client:
        response = client.post("/api/fill/start")
        return response.get_json()["task_id"]
