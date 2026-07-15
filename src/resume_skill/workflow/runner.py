"""Workflow runner for LangGraph application."""

from typing import Dict, Any, Optional
from .state import ApplicationState
from .graph import get_application_graph, build_application_graph


def build_application_graph() -> Any:
    """Build the application workflow graph.
    
    Returns:
        Compiled LangGraph StateGraph
    """
    return get_application_graph()


def run_application_workflow(initial_state: ApplicationState) -> Dict[str, Any]:
    """Run the application workflow with initial state.
    
    Args:
        initial_state: Initial workflow state
        
    Returns:
        Final workflow state after execution
    """
    print(f"[run_application_workflow] Starting workflow for task: {initial_state.get('task_id')}")
    
    # Build or get the graph
    graph = build_application_graph()
    
    # Run the workflow
    try:
        # Initialize state with default values if not provided
        state = {
            "task_id": initial_state.get("task_id", "unknown"),
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
            "_chrome_client": initial_state.get("_chrome_client"),
            "_llm_client": initial_state.get("_llm_client"),
            "_vision_client": initial_state.get("_vision_client"),
        }
        
        # Run the graph
        result = graph.invoke(state)
        
        print(f"[run_application_workflow] Workflow completed for task: {initial_state.get('task_id')}")
        print(f"[run_application_workflow] Success: {result.get('success', False)}")
        print(f"[run_application_workflow] Manual required: {result.get('manual_required', False)}")
        print(f"[run_application_workflow] Total steps: {len(result.get('execution_history', []))}")
        
        return result
        
    except Exception as e:
        print(f"[run_application_workflow] Error running workflow: {e}")
        
        # Return error state
        error_state = initial_state.copy()
        error_state.update({
            "success": False,
            "errors": initial_state.get("errors", []) + [str(e)],
            "manual_required": True,
            "execution_history": initial_state.get("execution_history", []) + [
                {"step": "workflow_runner", "status": "error", "message": f"Workflow failed: {e}"}
            ]
        })
        
        return error_state


def run_workflow_step_by_step(initial_state: ApplicationState, max_steps: int = 10) -> Dict[str, Any]:
    """Run workflow step by step for debugging.
    
    Args:
        initial_state: Initial workflow state
        max_steps: Maximum number of steps to run
        
    Returns:
        Final workflow state
    """
    print(f"[run_workflow_step_by_step] Running workflow step by step for task: {initial_state.get('task_id')}")
    
    graph = build_application_graph()
    state = initial_state.copy()
    
    for step in range(max_steps):
        print(f"\n--- Step {step + 1} ---")
        print(f"Current task: {state.get('current_task', 'unknown')}")
        print(f"Success: {state.get('success', False)}")
        print(f"Retry count: {state.get('retry_count', 0)}")
        
        try:
            # Run one step
            state = graph.invoke(state)
            
            # Check if we reached end state
            if state.get("current_task") == "end":
                print(f"[run_workflow_step_by_step] Reached end state at step {step + 1}")
                break
                
        except Exception as e:
            print(f"[run_workflow_step_by_step] Error at step {step + 1}: {e}")
            state["errors"] = state.get("errors", []) + [str(e)]
            state["manual_required"] = True
            break
    
    return state
