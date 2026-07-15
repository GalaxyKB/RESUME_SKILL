"""LangGraph workflow graph definition."""

try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    # Create dummy classes for when langgraph is not installed
    class END: pass
    
    class StateGraph:
        def __init__(self, state_type):
            pass
        def add_node(self, *args, **kwargs):
            return self
        def add_edge(self, *args, **kwargs):
            return self
        def add_conditional_edges(self, *args, **kwargs):
            return self
        def compile(self):
            return DummyGraph()


class DummyGraph:
    """Dummy graph for when langgraph is not installed."""
    def invoke(self, state):
        return state


from typing import Dict, Any, Literal
from .state import ApplicationState
from .nodes import (
    resume_analyzer_node,
    job_description_analyzer_node,
    resume_customization_node,
    cover_letter_generator_node,
    application_planner_node,
    browser_executor_node,
    verify_result_node,
    gui_recovery_node,
)


def build_application_graph() -> StateGraph:
    """Build the LangGraph StateGraph for application workflow."""
    
    if not HAS_LANGGRAPH:
        print("WARNING: langgraph not installed, returning dummy graph")
        return StateGraph(ApplicationState)
    
    # Create the graph
    workflow = StateGraph(ApplicationState)
    
    # Add nodes
    workflow.add_node("resume_analyzer", resume_analyzer_node)
    workflow.add_node("job_description_analyzer", job_description_analyzer_node)
    workflow.add_node("resume_customizer", resume_customization_node)
    workflow.add_node("cover_letter_generator", cover_letter_generator_node)
    workflow.add_node("application_planner", application_planner_node)
    workflow.add_node("browser_executor", browser_executor_node)
    workflow.add_node("verify_result", verify_result_node)
    workflow.add_node("gui_recovery", gui_recovery_node)
    
    # Define conditional routing function
    def route_after_verification(state: ApplicationState) -> Literal["end", "gui_recovery", "application_planner"]:
        """Route based on verification result."""
        success = state.get("success", False)
        manual_required = state.get("manual_required", False)
        gui_recovery_needed = state.get("gui_recovery_needed", False)
        
        if success:
            print("[route_after_verification] Success -> END")
            return "end"
        elif manual_required:
            print("[route_after_verification] Manual required -> END")
            return "end"
        elif gui_recovery_needed:
            print("[route_after_verification] GUI recovery needed -> gui_recovery")
            return "gui_recovery"
        else:
            print("[route_after_verification] Replanning needed -> application_planner")
            return "application_planner"
    
    # Define routing after GUI recovery
    def route_after_recovery(state: ApplicationState) -> Literal["application_planner"]:
        """Route after GUI recovery."""
        return "application_planner"
    
    # Build the main workflow path
    workflow.set_entry_point("application_planner")
    workflow.add_edge("application_planner", "browser_executor")
    workflow.add_edge("browser_executor", "verify_result")
    
    # Add conditional edges after verification
    workflow.add_conditional_edges(
        "verify_result",
        route_after_verification,
        {
            "end": END,
            "gui_recovery": "gui_recovery",
            "application_planner": "application_planner",
        }
    )
    
    # Add edge from GUI recovery back to planner
    workflow.add_edge("gui_recovery", "application_planner")
    
    # Optional: Add preprocessing path (not in main flow yet)
    # workflow.add_edge("resume_analyzer", "job_description_analyzer")
    # workflow.add_edge("job_description_analyzer", "resume_customizer")
    # workflow.add_edge("resume_customizer", "cover_letter_generator")
    # workflow.add_edge("cover_letter_generator", "application_planner")
    
    return workflow.compile()


# Create singleton graph instance
_application_graph = None


def get_application_graph() -> StateGraph:
    """Get or create the application graph instance."""
    global _application_graph
    if _application_graph is None:
        _application_graph = build_application_graph()
    return _application_graph