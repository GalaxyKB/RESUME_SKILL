"""
Apply agent - browser automation, form extraction, matching, and filling.

v2.4: The MCP Agent path (agent/mcp/agent.py) uses Google Chrome DevTools MCP.
The classical path (workflow.py) is still available for backward compatibility.
"""

from .workflow import run_apply_flow, RunOptions

__all__ = ["run_apply_flow", "RunOptions"]
