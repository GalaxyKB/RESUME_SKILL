"""MCP (Model Context Protocol) server and client for browser automation."""

from .client import MCPClient
from .server import TOOL_HELP

__all__ = ["MCPClient", "TOOL_HELP"]
