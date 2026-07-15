# LangGraph 工作流快速入门

## 5 分钟快速启动

### 1. 环境准备

```bash
# 激活 Python 3.11 虚拟环境
conda activate resume-skill-v24

# 进入项目目录
cd /path/to/RESUME_SKILL
```

### 2. 安装依赖

```bash
# 安装项目和所有依赖
pip install -e .

# 或单独安装 LangGraph（如已安装可跳过）
pip install langgraph>=0.0.40
```

### 3. 验证安装

```bash
# 运行检查脚本
python scripts/check_config.py
# 输出: ✓✓✓ All security checks passed! ✓✓✓

# 或运行安装验证
python scripts/install_workflow.py
# 输出: ✓✓✓ Installation verified successfully! ✓✓✓
```

### 4. 导入模块

```python
from resume_skill.workflow import (
    ApplicationState,
    build_application_graph,
    run_application_workflow,
    create_task,
    get_task,
)

print("✓ All modules imported successfully!")
```

---

## 基础使用

### 构建工作流图

```python
from resume_skill.workflow import build_application_graph

# 构建工作流图（单例模式，只初始化一次）
graph = build_application_graph()

print("✓ Graph built successfully")
```

### 创建任务

```python
from resume_skill.workflow import create_task

# 创建新任务
initial_state = {
    "user_profile": {
        "name": "张三",
        "email": "zhangsan@example.com",
    },
    "resume_data": {
        "summary": "资深软件工程师，10年工作经验",
    },
    "job_description": {
        "title": "高级Python工程师",
        "company": "某科技公司",
    },
}

task_id = create_task(initial_state)
print(f"✓ Task created: {task_id}")
```

### 运行工作流

```python
from resume_skill.workflow import run_application_workflow

# 运行工作流
result = run_application_workflow(initial_state)

# 检查结果
print(f"Success: {result.get('success', False)}")
print(f"Manual required: {result.get('manual_required', False)}")
print(f"Execution steps: {len(result.get('execution_history', []))}")
```

### 查询任务状态

```python
from resume_skill.workflow import get_task, get_task_logs

# 获取任务状态
task = get_task(task_id)
print(f"Task status: {task['status']}")
print(f"Current task: {task['state']['current_task']}")

# 获取任务日志
logs = get_task_logs(task_id, limit=10)
for log in logs:
    print(f"[{log['level']}] {log['message']}")
```

---

## 完整示例

### 简单端到端流程

```python
#!/usr/bin/env python
"""Simple end-to-end workflow example."""

from resume_skill.workflow import (
    ApplicationState,
    build_application_graph,
    create_task,
    get_task,
    run_application_workflow,
    append_log,
)


def main():
    # 1. 初始化
    print("=" * 70)
    print("RESUME_SKILL - Workflow Example")
    print("=" * 70)
    print()
    
    # 2. 创建任务
    print("Creating task...")
    initial_state = {
        "user_profile": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+1-234-567-8900",
        },
        "resume_data": {
            "summary": "Experienced software engineer",
            "skills": ["Python", "JavaScript", "React"],
        },
        "job_description": {
            "title": "Senior Engineer",
            "company": "TechCorp",
            "requirements": ["5+ years experience", "Python knowledge"],
        },
        "max_retries": 3,
    }
    
    task_id = create_task(initial_state)
    print(f"✓ Task created: {task_id}")
    print()
    
    # 3. 运行工作流
    print("Running workflow...")
    result = run_application_workflow(initial_state)
    print()
    
    # 4. 检查结果
    print("=" * 70)
    print("Workflow Results")
    print("=" * 70)
    print(f"Success: {result.get('success', False)}")
    print(f"Manual required: {result.get('manual_required', False)}")
    print(f"Total retries: {result.get('retry_count', 0)}")
    print(f"Execution steps: {len(result.get('execution_history', []))}")
    print()
    
    # 5. 查看执行历史
    print("Execution History:")
    for i, step in enumerate(result.get('execution_history', []), 1):
        print(f"  {i}. {step.get('step', 'unknown')} - {step.get('status', 'unknown')}")
    print()
    
    # 6. 获取任务信息
    print("Task Status:")
    task = get_task(task_id)
    if task:
        print(f"  Status: {task.get('status')}")
        print(f"  Created: {task.get('created_at')}")
        print(f"  Updated: {task.get('updated_at')}")


if __name__ == "__main__":
    main()
```

运行示例：
```bash
python examples/workflow_example.py
```

---

## State 定义

### ApplicationState 结构

```python
from typing import TypedDict, Optional, List, Dict, Any
from typing_extensions import NotRequired


class ApplicationState(TypedDict):
    # 任务标识
    task_id: str
    
    # 输入数据
    user_profile: Dict[str, Any]
    resume_data: Dict[str, Any]
    resume_pdf_path: str
    job_description: Dict[str, Any]
    
    # 生成的内容
    application_form: Dict[str, Any]
    generated_documents: Dict[str, Any]
    
    # 浏览器执行上下文
    browser_context: Dict[str, Any]
    
    # 工作流状态
    current_task: str
    next_action: str
    execution_history: List[Dict[str, Any]]
    errors: List[str]
    
    # 恢复和手动干预标志
    gui_recovery_needed: bool
    manual_required: bool
    
    # 成功指示
    success: bool
    
    # 重试管理
    retry_count: int
    max_retries: int
    
    # 可选扩展字段
    metadata: NotRequired[Dict[str, Any]]
    visual_verification_result: NotRequired[Dict[str, Any]]
    llm_decision_log: NotRequired[List[Dict[str, Any]]]
```

---

## 工作流路由

### 基础流程

```
START 
  ↓
application_planner
  ↓
browser_executor
  ↓
verify_result
  ├─ success=True ────→ END
  ├─ manual=True ────→ END
  ├─ retry_count >= max_retries ──→ manual=True → END
  └─ gui_recovery_needed=True → gui_recovery → application_planner (循环)
```

### 路由条件

| 条件 | 结果 | 说明 |
|------|------|------|
| `success == True` | 终止流程 | 验证通过 |
| `manual_required == True` | 终止流程 | 需要人工干预 |
| `gui_recovery_needed == True` | 调用恢复 | 尝试自动恢复 |
| `retry_count >= max_retries` | 标记手动 | 超过最大重试次数 |

---

## 任务存储 API

### 创建任务

```python
from resume_skill.workflow import create_task

task_id = create_task({
    "user_profile": {...},
    "resume_data": {...},
    ...
})
```

### 查询任务

```python
from resume_skill.workflow import get_task

task = get_task(task_id)
# 返回: {"task_id": "...", "status": "...", "state": {...}, ...}
```

### 更新任务

```python
from resume_skill.workflow import update_task

update_task(task_id, {
    "state": {
        "success": True,
    },
    "status": "completed",
})
```

### 日志记录

```python
from resume_skill.workflow import append_log

append_log(task_id, "Starting workflow", "info")
append_log(task_id, "Verification failed", "warning", {"code": 500})
```

### 查看日志

```python
from resume_skill.workflow import get_task_logs

logs = get_task_logs(task_id, limit=20)
for log in logs:
    print(f"[{log['level']}] {log['message']}")
```

---

## 常见问题

### Q: 如何安装 LangGraph？

A: 运行以下命令：
```bash
pip install langgraph>=0.0.40
```

### Q: 如何验证安装？

A: 运行检查脚本：
```bash
python scripts/install_workflow.py
```

### Q: 如何使用特定的 Python 版本？

A: 指定虚拟环境：
```bash
/path/to/venv/python -m pip install -e .
```

### Q: 节点函数如何编写？

A: 节点函数接收 state 字典，返回更新的字段：
```python
def my_node(state: ApplicationState) -> Dict[str, Any]:
    # 读取 state
    task_id = state.get("task_id")
    
    # 执行逻辑
    result = do_something()
    
    # 返回更新的字段
    return {
        "current_task": "next_task",
        "execution_history": state.get("execution_history", []) + [
            {"step": "my_node", "status": "completed", "result": result}
        ]
    }
```

### Q: 如何添加新的条件路由？

A: 在 `graph.py` 中修改 `route_after_verification` 函数：
```python
def route_after_verification(state: ApplicationState) -> Literal["end", "path1", "path2"]:
    if some_condition:
        return "path1"
    elif another_condition:
        return "path2"
    else:
        return "end"
```

---

## 更多资源

- [LangGraph 官方文档](https://python.langchain.com/docs/langgraph/)
- [项目 README](../README.md)
- [验收清单](../WORKFLOW_ACCEPTANCE.md)
- [API 参考](./WORKFLOW_API.md) (待编写)

---

**最后更新**: 2026-07-14  
**版本**: v2.4-workflow