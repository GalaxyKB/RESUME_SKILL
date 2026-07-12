"""
MCP Server: exposes browser automation tools via stdio JSON-RPC.

Usage:
    python server.py  (reads JSON-RPC from stdin, writes to stdout)

IMPORTANT: stdout is reserved for JSON-RPC protocol.
All non-JSON output (print, logging) must go to stderr.
"""

from __future__ import annotations

import builtins
import json
import sys
import traceback

# Redirect built-in print to stderr so imported modules' print() doesn't corrupt JSON-RPC
_print_original = builtins.print
def _print_stderr(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    _print_original(*args, **kwargs)
builtins.print = _print_stderr

# Also redirect sys.stdout to stderr so any direct sys.stdout.write goes to stderr
_stdout_for_rpc = sys.stdout
sys.stdout = sys.stderr
TOOL_HELP = {
    "wait_for_user": {
        "description": "等待用户手动操作（如登录），用户按下回车后继续",
        "params": {
            "message": {"type": "string", "description": "提示信息", "default": "请完成操作后按 Enter 继续..."},
        }
    },
}


def cmd_wait_for_user(message: str = "请完成操作后按 Enter 继续...") -> dict:
    input(message)
    return {"status": "continue"}




TOOL_ROUTES = {
    "wait_for_user": cmd_wait_for_user,
    "help": lambda **kwargs: {"tools": {k: v["description"] for k, v in TOOL_HELP.items()}},
}


def handle_request(request: dict) -> dict:
    request_id = request.get("id", 0)
    method = request.get("method", "")
    params = request.get("params", {})

    if method not in TOOL_ROUTES:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Unknown tool: {method}"},
        }

    try:
        if isinstance(params, dict):
            result = TOOL_ROUTES[method](**params)
        else:
            result = TOOL_ROUTES[method](params)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": str(e), "traceback": traceback.format_exc()},
        }


def main() -> None:
    global _stdout_for_rpc
    sys.stderr.write("[MCP Server] Started. Waiting for JSON-RPC on stdin...\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
        except json.JSONDecodeError as e:
            response = {
                "jsonrpc": "2.0",
                "id": 0,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
        _stdout_for_rpc.write(json.dumps(response, ensure_ascii=False) + "\n")
        _stdout_for_rpc.flush()


if __name__ == "__main__":
    try:
        main()
    finally:
        # Restore original print and stdout
        builtins.print = _print_original
        sys.stdout = _stdout_for_rpc
