"""
MCP Client: connects to MCP Server via stdio subprocess.

Usage:
    client = MCPClient()
    client.connect()
    result = client.call_tool("browser_start", {"session_dir": ".session/chrome"})
    client.close()
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class MCPClient:
    def __init__(self, use_mcp_sdk: bool = False, mcp_python_path: str = ""):
        self._process: subprocess.Popen | None = None
        self._next_id = 1
        self._use_mcp_sdk = use_mcp_sdk
        self._mcp_python_path = mcp_python_path
        self._session = None  # MCP SDK session
        self._read = None
        self._write = None
        self._stdio = None
        self._loop: asyncio.AbstractEventLoop | None = None  # ← 新增：共享事件循环

    def connect(self) -> None:
        if self._process is not None:
            return
        if self._use_mcp_sdk:
            try:
                self._connect_mcp_sdk()
            except ImportError:
                # MCP SDK不可用，回退到Legacy模式
                print("[MCP Client] ⚠️ MCP SDK not available, falling back to Legacy mode")
                self._use_mcp_sdk = False
                self._connect_legacy()
        else:
            self._connect_legacy()

    def _connect_legacy(self) -> None:
        """原有 JSON-RPC 子进程方式（不变）"""
        server_script = str(Path(__file__).parent / "server.py")
        python_exe = self._mcp_python_path or sys.executable
        self._process = subprocess.Popen(
            [python_exe, server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        # Wait for server ready message on stderr
        time.sleep(0.5)

    def _connect_mcp_sdk(self) -> None:
        """使用 MCP SDK 的 stdio_client 连接"""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as e:
            raise ImportError(
                "MCP SDK not available. Install with: pip install mcp>=1.0"
            ) from e

        # 创建新的事件循环
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        # 运行异步连接
        self._loop.run_until_complete(self._async_connect())
    
    async def _async_connect(self):
        """异步连接函数"""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        
        server_script = str(Path(__file__).parent / "server_mcp.py")
        python_exe = self._mcp_python_path or sys.executable
        server_params = StdioServerParameters(
            command=python_exe,
            args=[server_script],
        )
        
        async with stdio_client(server_params) as (self._read, self._write):
            async with ClientSession(self._read, self._write) as self._session:
                await self._session.initialize()

    def call_tool(self, name: str, params: dict[str, Any] | None = None) -> Any:
        if self._use_mcp_sdk:
            return self._call_tool_mcp(name, params)
        else:
            return self._call_tool_with_retry(name, params)

    def _call_tool_legacy(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """原有 JSON-RPC 调用方式（不变）"""
        if self._process is None:
            raise RuntimeError("Not connected. Call connect() first.")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": name,
            "params": params or {},
        }
        self._next_id += 1

        request_str = json.dumps(request, ensure_ascii=False)
        self._process.stdin.write(request_str + "\n")
        self._process.stdin.flush()

        response_line = self._process.stdout.readline()
        if not response_line:
            stderr_output = self._process.stderr.read()
            raise RuntimeError(
                f"MCP Server process ended unexpectedly.\n"
                f"Return code: {self._process.poll()}\n"
                f"Stderr: {stderr_output}"
            )

        response = json.loads(response_line)

        if "error" in response:
            raise RuntimeError(
                f"Tool '{name}' error: {response['error'].get('message', 'Unknown')}"
            )

        return response.get("result")

    def _call_tool_mcp(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """MCP SDK 方式调用"""
        import json

        async def _async_call_impl():
            result = await self._session.call_tool(name, params or {})
            if result.content and len(result.content) > 0:
                text = result.content[0].text
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return {"raw_text": text}  # ← 总是返回 dict
            return {}

        return self._loop.run_until_complete(_async_call_impl())

    def _call_tool_with_retry(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """Legacy模式下的重试逻辑"""
        try:
            return self._call_tool_legacy(name, params)
        except (BrokenPipeError, ConnectionError, RuntimeError) as e:
            # Server crash detected, try to reconnect and retry once
            if "process ended unexpectedly" in str(e) or isinstance(e, (BrokenPipeError, ConnectionError)):
                print(f"[MCP Client] Server crash detected, attempting reconnect...")
                self.close()
                self.connect()
                return self._call_tool_legacy(name, params)
            else:
                # Re-raise other RuntimeError
                raise e

    def close(self) -> None:
        if self._use_mcp_sdk and self._session is not None and self._loop is not None:
            async def _async_close():
                # Session and stdio are closed automatically by async with
                pass
            self._loop.run_until_complete(_async_close())
            self._loop.close()
            self._loop = None
        elif self._process:
            try:
                self._call_tool_legacy("browser_close")
            except Exception:
                pass
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()