"""
MCP Server using official MCP Python SDK (FastMCP).
Requires: mcp>=1.0, Python>=3.10
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("resume-skill")

@mcp.tool()
def wait_for_user(message: str = "请完成操作后按 Enter 继续...") -> str:
    """等待用户手动操作（如登录），用户按下回车后继续"""
    input(message)
    return json.dumps({"status": "continue"}, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport="stdio")