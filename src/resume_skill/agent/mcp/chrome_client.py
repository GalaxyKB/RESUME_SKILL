"""
MCP Client for Google Chrome DevTools MCP server (chrome-devtools-mcp).
Communicates via stdio JSON-RPC with npx chrome-devtools-mcp subprocess.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from typing import Any


class ChromeDevToolsClient:
    def __init__(self, headless: bool = False):
        self._headless = headless
        self._process: subprocess.Popen | None = None
        self._next_id = 1
        self._lock = threading.Lock()
        self._buffer: str = ""

    def connect(self) -> None:
        args = ["-y", "chrome-devtools-mcp@latest"]
        if self._headless:
            args.append("--headless")
        args.append("--isolated")

        command_args = ["npx"] + args
        print(f"[ChromeDevTools] 启动: {' '.join(command_args)}")
        use_shell = sys.platform == "win32"
        self._process = subprocess.Popen(
            " ".join(command_args) if use_shell else command_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            shell=use_shell,
        )

        # Wait for process to start, then do MCP initialize
        for _ in range(60):
            if self._process and self._process.poll() is not None:
                raise RuntimeError("chrome-devtools-mcp 进程启动失败")
            time.sleep(0.5)

            resp = self._call("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "resume-skill", "version": "2.4.0"},
            })
            if resp is not None:
                print(f"[ChromeDevTools] 初始化成功")
                return

        raise RuntimeError("chrome-devtools-mcp 初始化超时")

    def _call(self, method: str, params: dict, timeout_sec: int = 30) -> Any:
        """Send a JSON-RPC call and wait for response with timeout."""
        if not self._process:
            raise RuntimeError("Not connected")

        request_id = self._next_id
        self._next_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        with self._lock:
            self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self._process.stdin.flush()

            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                if self._process.poll() is not None:
                    raise RuntimeError("chrome-devtools-mcp 进程已退出")
                line = self._process.stdout.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    response = json.loads(line)
                    rid = response.get("id")
                    if rid == request_id:
                        if "error" in response:
                            err = response["error"]
                            raise RuntimeError(f"工具调用错误: {err.get('message', err)}")
                        return response.get("result")
                    # 其他请求的响应，忽略（并发情况极少出现）
                except json.JSONDecodeError:
                    continue

        raise TimeoutError(f"chrome-devtools-mcp 调用 {method} 超时 ({timeout_sec}s)")

    def call_tool(self, name: str, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
        result = self._call("tools/call", {"name": name, "arguments": params or {}}, timeout_sec=timeout)
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
                self._process.kill()
            self._process = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
