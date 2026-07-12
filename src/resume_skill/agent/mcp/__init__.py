"""
MCP module - v2.4 uses dual MCP servers (ours + Google Chrome DevTools).
"""

from .client import MCPClient
from .chrome_client import ChromeDevToolsClient

__all__ = ["MCPClient", "ChromeDevToolsClient"]