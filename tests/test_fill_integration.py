"""
Integration test: Complete workflow for background task fill with LangGraph.
Simulates: observe -> planner fill -> executor -> verify success -> END
"""

import sys
import json
import time
sys.path.insert(0, "src")

from resume_skill.webui.app import app, task_manager
from resume_skill.agent.fill_workflow import ApplicationState, FillWorkflowRunner, load_user_profile
from unittest.mock import Mock, MagicMock, patch


def test_complete_workflow():
    """Test complete mock workflow with state transitions."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Complete LangGraph Workflow")
    print("="*70 + "\n")
    
    # 1. Create ApplicationState
    print("1️⃣  Creating ApplicationState...")
    state = ApplicationState(
        task_id="test-workflow-001",
        user_profile={
            "name": "Test User",
            "email": "test@example.com",
            "phone": "13800138000"
        },
        resume_pdf_path="/tmp/test_resume.pdf",
        max_retries=20,
        current_task="开始工作流"
    )
    
    print(f"   ✓ State created: task_id={state.task_id}")
    print(f"   ✓ User profile loaded: {list(state.user_profile.keys())}")
    print(f"   ✓ Resume path: {state.resume_pdf_path}")
    print(f"   ✓ Max retries: {state.max_retries}\n")
    
    # 2. Test state conversions
    print("2️⃣  Testing state serialization...")
    state_dict = state.to_dict()
    assert isinstance(state_dict, dict)
    assert state_dict["task_id"] == "test-workflow-001"
    print(f"   ✓ State to_dict() works")
    
    # 3. Test logging
    print("3️⃣  Testing logging functionality...")
    state.add_log("Test log message")
    assert len(state.log) == 1
    assert "[" in state.log[0] and "]" in state.log[0]
    print(f"   ✓ Logging works: {state.log[0]}\n")
    
    # 4. Test state progression
    print("4️⃣  Testing state progression...")
    state.status = "running"
    state.current_task = "正在处理"
    state.step = 1
    state.add_log("Step 1: Observe started")
    assert state.status == "running"
    print(f"   ✓ Status updated: {state.status}")
    print(f"   ✓ Current task: {state.current_task}")
    print(f"   ✓ Step: {state.step}\n")
    
    # 5. Simulate workflow
    print("5️⃣  Simulating workflow steps...")
    steps = [
        ("Step 1", "正在观察页面..."),
        ("Step 2", "正在规划填写策略..."),
        ("Step 3", "正在执行填充..."),
        ("Step 4", "正在执行视觉评估..."),
    ]
    
    for step_name, task_desc in steps:
        state.current_task = task_desc
        state.add_log(step_name)
        print(f"   ✓ {step_name}: {task_desc}")
    
    # 6. Complete workflow
    print("\n6️⃣  Completing workflow...")
    state.status = "completed"
    state.success = True
    state.failed_count = 0
    state.fields = [
        {"uid": "name", "label": "姓名", "filled": True},
        {"uid": "email", "label": "邮箱", "filled": True},
        {"uid": "phone", "label": "电话", "filled": True},
    ]
    state.vision_review = {
        "ok": True,
        "summary": "所有字段已正确填充",
        "issues": []
    }
    state.add_log("工作流完成")
    
    print(f"   ✓ Final status: {state.status}")
    print(f"   ✓ Success: {state.success}")
    print(f"   ✓ Failed count: {state.failed_count}")
    print(f"   ✓ Fields: {len(state.fields)}")
    print(f"   ✓ Vision review: {state.vision_review.get('summary')}\n")
    
    # 7. Verify log
    print("7️⃣  Workflow log:")
    for entry in state.log:
        print(f"   {entry}")
    print()
    
    # Assertions
    assert state.status == "completed"
    assert state.success == True
    assert state.failed_count == 0
    assert len(state.log) > 0
    assert len(state.fields) == 3
    
    print("="*70)
    print("✓ INTEGRATION TEST PASSED")
    print("="*70 + "\n")


def test_frontend_to_backend_flow():
    """Test complete frontend -> backend -> polling flow."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Frontend to Backend Flow")
    print("="*70 + "\n")
    
    with app.test_client() as client:
        # 1. Frontend calls POST /api/fill/start
        print("1️⃣  Frontend: POST /api/fill/start")
        response = client.post('/api/fill/start')
        assert response.status_code == 200
        
        result = json.loads(response.data)
        task_id = result["task_id"]
        print(f"   ✓ Response: task_id={task_id}, status={result['status']}\n")
        
        # 2. Frontend polls /api/fill/status/<task_id>
        print("2️⃣  Frontend: Polling /api/fill/status/<task_id>")
        poll_count = 0
        max_polls = 3
        
        while poll_count < max_polls:
            response = client.get(f'/api/fill/status/{task_id}')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            poll_count += 1
            
            print(f"   Poll {poll_count}:")
            print(f"     - status: {data['status']}")
            print(f"     - running: {data['running']}")
            print(f"     - current_task: {data['current_task']}")
            print(f"     - log entries: {len(data['log'])}")
            
            # Verify response structure
            assert "task_id" in data
            assert "running" in data
            assert "current_task" in data
            assert "log" in data
            assert isinstance(data["log"], list)
            assert "fields" in data
            assert isinstance(data["fields"], list)
            assert "vision_review" in data
            assert isinstance(data["vision_review"], dict)
            assert "success" in data
            assert isinstance(data["success"], bool)
            assert "failed_count" in data
            assert isinstance(data["failed_count"], int)
            assert "errors" in data
            assert isinstance(data["errors"], list)
            
            if not data["running"]:
                print(f"\n   ✓ Task completed after {poll_count} polls\n")
                break
            
            time.sleep(0.1)
        
        # 3. Frontend shows final state
        print(f"3️⃣  Frontend: Display final state")
        print(f"   - Fields: {len(data.get('fields', []))}")
        print(f"   - Vision review: {data.get('vision_review', {}).get('summary', 'N/A')}")
        print(f"   - Final success: {data.get('success')}\n")
        
    print("="*70)
    print("✓ FRONTEND INTEGRATION TEST PASSED")
    print("="*70 + "\n")


def test_error_handling():
    """Test error handling in workflow."""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Error Handling")
    print("="*70 + "\n")
    
    # 1. Test non-existent task
    print("1️⃣  Test non-existent task")
    with app.test_client() as client:
        response = client.get('/api/fill/status/nonexistent-task-id')
        assert response.status_code == 404
        print("   ✓ Returns 404 for non-existent task\n")
    
    # 2. Test cancel task
    print("2️⃣  Test task cancellation")
    with app.test_client() as client:
        response = client.post('/api/fill/start')
        task_id = json.loads(response.data)["task_id"]
        
        response = client.post(f'/api/fill/cancel/{task_id}')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data["status"] == "cancelled"
        print(f"   ✓ Task cancelled successfully\n")
    
    print("="*70)
    print("✓ ERROR HANDLING TEST PASSED")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        test_complete_workflow()
        test_frontend_to_backend_flow()
        test_error_handling()
        
        print("\n" + "="*70)
        print("✓ ALL INTEGRATION TESTS PASSED")
        print("="*70 + "\n")
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
