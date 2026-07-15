"""RESUME_SKILL LangGraph workflow module."""

# Check for required dependencies
try:
    import langgraph
except ImportError:
    raise ImportError(
        "\n"
        "=" * 70 + "\n"
        "ERROR: LangGraph is not installed!\n"
        "=" * 70 + "\n"
        "\n"
        "The LangGraph workflow module requires the 'langgraph' package.\n"
        "\n"
        "Please install it using one of these methods:\n"
        "\n"
        "  Option 1: Install the full resume-skill package with LangGraph support\n"
        "    pip install -e . --upgrade\n"
        "\n"
        "  Option 2: Install langgraph directly\n"
        "    pip install langgraph>=0.0.40\n"
        "\n"
        "  Option 3: Install with workflow extras\n"
        "    pip install -e '.[workflow]'\n"
        "\n"
        "After installation, verify with:\n"
        "    python -c 'import langgraph; print(\"✓ LangGraph is ready\")'\n"
        "\n"
        "For more information, visit: https://github.com/langgraph-js/langgraph\n"
        "=" * 70 + "\n"
    )

from .state import ApplicationState
from .graph import build_application_graph
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
from .browser_executor import BrowserExecutorNode
from .runner import run_application_workflow
from .store import create_task, get_task, update_task, append_log

__all__ = [
    "ApplicationState",
    "build_application_graph",
    "resume_analyzer_node",
    "job_description_analyzer_node",
    "resume_customization_node",
    "cover_letter_generator_node",
    "application_planner_node",
    "browser_executor_node",
    "verify_result_node",
    "gui_recovery_node",
    "BrowserExecutorNode",
    "run_application_workflow",
    "create_task",
    "get_task",
    "update_task",
    "append_log",
]