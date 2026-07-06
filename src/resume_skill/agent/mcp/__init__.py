"""MCP (Model Context Protocol) server and client for browser automation."""

from .client import MCPClient
from .server import TOOL_HELP

try:
    # server_mcp.py 需要 mcp SDK，可能在旧环境不可用
    from . import server_mcp
    _mcp_sdk_available = True
except ImportError:
    _mcp_sdk_available = False

__all__ = ["MCPClient", "TOOL_HELP", "_mcp_sdk_available"]