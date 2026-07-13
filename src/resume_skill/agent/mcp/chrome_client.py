"""
MCP Client for Google Chrome DevTools MCP server (chrome-devtools-mcp).
Communicates via stdio JSON-RPC with npx chrome-devtools-mcp subprocess.
Uses binary pipe to avoid Windows GBK encoding issues.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import Any


class ChromeDevToolsClient:
    def __init__(self, headless: bool = False):
        self._headless = headless
        self._process: subprocess.Popen | None = None
        self._next_id = 1
        self._partial = b""  # leftover bytes from previous read

    def connect(self) -> None:
        args = ["-y", "chrome-devtools-mcp@latest"]
        if self._headless:
            args.append("--headless")
        args.append("--isolated")

        cmd = " ".join(["npx"] + args) if sys.platform == "win32" else ["npx"] + args
        use_shell = sys.platform == "win32"
        print(f"[ChromeDevTools] 启动: {cmd}")
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            shell=use_shell,
        )
        # Don't use text=True - read bytes and decode as UTF-8

        # Wait for initialize response (up to 30s)
        for _ in range(60):
            if self._process.poll() is not None:
                _, stderr = self._process.communicate()
                raise RuntimeError(f"chrome-devtools-mcp 进程已退出: {stderr.decode('utf-8', errors='replace')[:200]}")
            time.sleep(0.5)
            resp = self._send_recv("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "resume-skill", "version": "2.4.0"},
            })
            if resp is not None:
                print(f"[ChromeDevTools] 初始化成功")
                return

        raise RuntimeError("chrome-devtools-mcp 初始化超时")

    def _read_line(self) -> str:
        """Read one line from stdout, decoding as UTF-8. Blocks until newline."""
        if not self._process or not self._process.stdout:
            raise RuntimeError("Not connected")
        while b"\n" not in self._partial:
            chunk = self._process.stdout.read(1)
            if not chunk:
                raise ConnectionError("chrome-devtools-mcp stdout 已关闭")
            self._partial += chunk
        idx = self._partial.index(b"\n")
        line = self._partial[:idx]
        self._partial = self._partial[idx + 1:]
        return line.decode("utf-8", errors="replace").strip()

    def _send_recv(self, method: str, params: dict, timeout_sec: int = 30) -> Any:
        """Send JSON-RPC request, return response result, or None if not matched."""
        if not self._process or not self._process.stdin:
            raise RuntimeError("Not connected")

        request_id = self._next_id
        self._next_id += 1

        request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        data = json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n"
        self._process.stdin.write(data)
        self._process.stdin.flush()

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                line = self._read_line()
            except ConnectionError:
                raise RuntimeError("chrome-devtools-mcp 连接已断开")
            if not line:
                time.sleep(0.05)
                continue
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if response.get("id") == request_id:
                if "error" in response:
                    err = response["error"]
                    raise RuntimeError(f"工具错误: {err.get('message', str(err))[:200]}")
                return response.get("result")
        return None

    def call_tool(self, name: str, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
        result = self._send_recv("tools/call", {"name": name, "arguments": params or {}}, timeout_sec=timeout)
        if result is None:
            raise TimeoutError(f"工具 {name} 调用超时 ({timeout}s)")
        if isinstance(result, dict) and "content" in result:
            if result["content"] and len(result["content"]) > 0:
                text = result["content"][0].get("text", "")
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return text
        return result

    def close(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
