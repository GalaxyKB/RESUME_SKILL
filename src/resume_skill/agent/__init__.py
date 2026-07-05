"""Apply agent - browser automation, form extraction, matching, and filling."""

from .workflow import run_apply_flow, RunOptions

try:
    from .mcp.client import MCPClient
    from .mcp.server import TOOL_HELP
    _mcp_available = True
except ImportError:
    _mcp_available = False

__all__ = ["run_apply_flow", "RunOptions"]
