"""
MCP Client: connects to MCP Server via stdio subprocess.

Usage:
    client = MCPClient()
    client.connect()
    result = client.call_tool("browser_start", {"session_dir": ".session/chrome"})
    client.close()
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class MCPClient:
    def __init__(self, server_script: str | None = None):
        self._process: subprocess.Popen | None = None
        self._next_id = 1
        if server_script is None:
            server_script = str(Path(__file__).parent / "server.py")
        self._server_script = server_script

    def connect(self) -> None:
        if self._process is not None:
            return
        self._process = subprocess.Popen(
            [sys.executable, self._server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        # Wait for server ready message on stderr
        time.sleep(0.5)

    def _call_tool(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """Internal method to call tool without retry logic."""
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

    def call_tool(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """Call tool with automatic reconnect on server crash."""
        try:
            return self._call_tool(name, params)
        except (BrokenPipeError, ConnectionError, RuntimeError) as e:
            # Server crash detected, try to reconnect and retry once
            if "process ended unexpectedly" in str(e) or isinstance(e, (BrokenPipeError, ConnectionError)):
                print(f"[MCP Client] Server crash detected, attempting reconnect...")
                self.close()
                self.connect()
                return self._call_tool(name, params)
            else:
                # Re-raise other RuntimeError
                raise e

    def close(self) -> None:
        if self._process:
            try:
                self.call_tool("browser_close")
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
