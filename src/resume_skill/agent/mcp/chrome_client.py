"""
Simplified MCP Client for Google Chrome DevTools MCP server (chrome-devtools-mcp).

For v2.4 development: uses simple subprocess communication instead of MCP SDK.
This is a temporary implementation for development purposes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from typing import Any


class ChromeDevToolsClient:
    """Simplified client for chrome-devtools-mcp using subprocess communication."""
    
    def __init__(self, headless: bool = False):
        self._headless = headless
        self._process = None
        self._next_id = 1
        
    def connect(self) -> None:
        """启动 chrome-devtools-mcp 子进程并建立连接。"""
        args = ["-y", "chrome-devtools-mcp@latest"]
        if self._headless:
            args.append("--headless")
        args.append("--isolated")
        
        command_args = ["npx"] + args
        print(f"启动 chrome-devtools-mcp: {' '.join(command_args)}")
        # Windows 需要 shell=True 因为 npx 是 npx.cmd（批处理文件）
        use_shell = sys.platform == "win32"
        self._process = subprocess.Popen(
            " ".join(command_args) if use_shell else command_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            shell=use_shell,
        )
        
        # 等待进程启动
        time.sleep(3)
        
        # 发送initialize请求
        init_request = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "resume-skill",
                    "version": "2.4.0"
                }
            }
        }
        self._next_id += 1
        
        self._send_request(init_request)
        
        # 等待并读取初始化响应
        response = self._read_response()
        if response and "result" in response:
            print("chrome-devtools-mcp 初始化成功")
        else:
            raise RuntimeError(f"chrome-devtools-mcp 初始化失败: {response}")
        
        # 获取工具列表以便调试
        try:
            tools_request = {
                "jsonrpc": "2.0",
                "id": self._next_id,
                "method": "tools/list",
                "params": {}
            }
            self._next_id += 1
            self._send_request(tools_request)
            tools_response = self._read_response()
            if tools_response and "result" in tools_response:
                tools = tools_response["result"].get("tools", [])
                print(f"可用工具: {len(tools)} 个")
        except Exception as e:
            print(f"获取工具列表失败（不影响使用）: {e}")
    
    def _send_request(self, request: dict) -> None:
        """发送 JSON-RPC 请求到子进程。"""
        if not self._process:
            raise RuntimeError("Not connected")
        
        json_str = json.dumps(request, ensure_ascii=False)
        self._process.stdin.write(json_str + "\n")
        self._process.stdin.flush()
    
    def _read_response(self) -> dict | None:
        """从子进程读取 JSON-RPC 响应。"""
        if not self._process:
            raise RuntimeError("Not connected")
        
        try:
            # 简单的超时机制
            for _ in range(10):
                line = self._process.stdout.readline()
                if line:
                    line = line.strip()
                    if line:
                        try:
                            return json.loads(line)
                        except json.JSONDecodeError:
                            # 可能是日志输出，继续读取
                            continue
                time.sleep(0.1)
        except Exception as e:
            print(f"读取响应时出错: {e}")
        
        return None
    
    def call_tool(self, name: str, params: dict[str, Any] | None = None) -> Any:
        """
        调用 chrome-devtools-mcp 工具。
        
        参数:
            name: 工具名，如 "navigate_page", "take_snapshot", "fill", "click"
            params: 工具参数字典
            
        返回:
            解析后的结果（dict、list 或 str）
        """
        if not self._process:
            raise RuntimeError("Not connected. Call connect() first.")
        
        request_id = self._next_id
        self._next_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": params or {}
            }
        }
        
        self._send_request(request)
        
        # 等待响应
        for _ in range(30):  # 最多等待3秒
            response = self._read_response()
            if response and response.get("id") == request_id:
                if "result" in response:
                    result = response["result"]
                    # 提取文本内容
                    if isinstance(result, dict) and "content" in result:
                        if result["content"] and len(result["content"]) > 0:
                            text = result["content"][0].get("text", "")
                            try:
                                return json.loads(text)
                            except (json.JSONDecodeError, TypeError):
                                return text
                    return result
                elif "error" in response:
                    raise RuntimeError(f"工具调用错误: {response['error']}")
            time.sleep(0.1)
        
        raise RuntimeError("等待响应超时")
    
    def close(self) -> None:
        """关闭与 chrome-devtools-mcp 的连接。"""
        if self._process:
            self._process.terminate()
            self._process.wait()
            self._process = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, *args):
        self.close()