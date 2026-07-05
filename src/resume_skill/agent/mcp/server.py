"""
MCP Server: exposes browser automation tools via stdio JSON-RPC.

Usage:
    python server.py  (reads JSON-RPC from stdin, writes to stdout)

IMPORTANT: stdout is reserved for JSON-RPC protocol.
All non-JSON output (print, logging) must go to stderr.
"""

from __future__ import annotations

import builtins
import concurrent.futures
import functools
import json
import sys
import traceback
from typing import Any

# Redirect built-in print to stderr so imported modules' print() doesn't corrupt JSON-RPC
_print_original = builtins.print
def _print_stderr(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    _print_original(*args, **kwargs)
builtins.print = _print_stderr

# Also redirect sys.stdout to stderr so any direct sys.stdout.write goes to stderr
_stdout_for_rpc = sys.stdout
sys.stdout = sys.stderr

def with_timeout(timeout_sec: int = 30):
    """Timeout decorator for tool functions."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout_sec)
                except concurrent.futures.TimeoutError:
                    return {"status": "timeout", "error": f"操作超过 {timeout_sec} 秒"}
        return wrapper
    return decorator

# Ensure parent package is accessible
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from resume_skill.agent.browser_agent import BrowserAgent
from resume_skill.agent.form_extractor import extract_fields_rule_based
from resume_skill.agent.form_filler import _fill_single_field, _verify_fill, _resolve_locator
from resume_skill.agent.utils import find_resume_pdf

browser: BrowserAgent | None = None
_resume_path: str = ""


def _get_page():
    if browser is None:
        raise RuntimeError("Browser not started. Call browser_start first.")
    return browser.page


TOOL_HELP = {
    "browser_start": {
        "description": "启动浏览器（headless=false，用户可见）",
        "params": {
            "session_dir": {"type": "string", "description": "会话目录路径，用于保存登录状态", "default": ".session/chrome"},
            "headless": {"type": "boolean", "description": "是否无头模式", "default": False},
            "slow_motion": {"type": "integer", "description": "操作延迟（毫秒）", "default": 300},
        }
    },
    "browser_navigate": {
        "description": "在浏览器中打开指定 URL",
        "params": {
            "url": {"type": "string", "description": "目标页面 URL"},
        }
    },
    "browser_close": {
        "description": "关闭浏览器",
        "params": {}
    },
    "get_page_text": {
        "description": "提取当前页面的文本内容（用于 JD 分析）",
        "params": {}
    },
    "extract_fields": {
        "description": "提取当前页面所有表单字段（规则通道）返回原始字段列表，需要后续匹配",
        "params": {}
    },
    "get_current_url": {
        "description": "获取当前页面URL",
        "params": {}
    },
    "match_fields": {
        "description": "匹配表单字段与用户档案（规则匹配，纯计算）",
        "params": {
            "fields_json": {"type": "string", "description": "字段列表JSON字符串"},
            "profile_json": {"type": "string", "description": "用户档案JSON字符串"}
        }
    },
    "fill_field": {
        "description": "填充单个表单字段（九策略自动降级）",
        "params": {
            "field_id": {"type": "string", "description": "字段 ID"},
            "selector": {"type": "string", "description": "CSS 选择器"},
            "value": {"type": "string", "description": "要填入的值"},
            "strategy": {"type": "string", "description": "填充策略", "default": "text"},
            "xpath": {"type": "string", "description": "XPath 选择器", "default": ""},
            "frame_url": {"type": "string", "description": "iframe URL（如有）", "default": ""},
            "field_label": {"type": "string", "description": "字段标签名", "default": ""},
            "tag": {"type": "string", "description": "HTML tag", "default": "input"},
            "field_type": {"type": "string", "description": "输入类型", "default": "text"},
            "role": {"type": "string", "description": "ARIA role", "default": ""},
        }
    },
    "verify_field": {
        "description": "校验单个字段是否填入了期望值",
        "params": {
            "selector": {"type": "string", "description": "CSS 选择器"},
            "expected_value": {"type": "string", "description": "期望值"},
            "xpath": {"type": "string", "description": "XPath", "default": ""},
            "frame_url": {"type": "string", "description": "iframe URL", "default": ""},
            "field_label": {"type": "string", "description": "字段标签", "default": ""},
            "tag": {"type": "string", "description": "HTML tag", "default": "input"},
            "field_type": {"type": "string", "description": "输入类型", "default": "text"},
        }
    },
    "find_and_click": {
        "description": "根据关键词查找按钮并点击（申请/提交）",
        "params": {
            "keywords": {"type": "array", "description": "关键词列表，如 ['提交', '申请']"},
        }
    },
    "wait_for_user": {
        "description": "等待用户手动操作（如登录），用户按下回车后继续",
        "params": {
            "message": {"type": "string", "description": "提示信息", "default": "请完成操作后按 Enter 继续..."},
        }
    },
}


@with_timeout(30)
def cmd_browser_start(session_dir: str = ".session/chrome", headless: bool = False, slow_motion: int = 300) -> dict:
    global browser
    if browser is not None:
        return {"status": "already_started"}
    browser = BrowserAgent(
        session_profile_dir=session_dir,
        keep_browser_open=True,
        headless=headless,
        slow_motion=slow_motion,
    )
    browser.start()
    return {"status": "started"}


@with_timeout(30)
def cmd_browser_navigate(url: str) -> dict:
    _get_page()
    browser.open_url(url)
    return {"status": "navigated", "url": url}


def cmd_browser_close() -> dict:
    """关闭浏览器（清理操作，不设超时）"""
    global browser
    if browser:
        try:
            browser.close()
        except Exception:
            pass  # 忽略关闭过程中的异常
        browser = None
    return {"status": "closed"}


@with_timeout(10)
def cmd_get_page_text() -> dict:
    text = browser.get_page_text()
    return {"text": text, "length": len(text)}


@with_timeout(15)
def cmd_extract_fields() -> dict:
    page = _get_page()
    fields = extract_fields_rule_based(page)
    return {"fields": fields, "count": len(fields)}


@with_timeout(15)
def cmd_fill_field(
    field_id: str = "",
    selector: str = "",
    value: str = "",
    strategy: str = "text",
    xpath: str = "",
    frame_url: str = "",
    field_label: str = "",
    tag: str = "input",
    field_type: str = "text",
    role: str = "",
) -> dict:
    page = _get_page()
    item: dict[str, Any] = {
        "field_id": field_id,
        "selector": selector,
        "xpath": xpath,
        "frame_url": frame_url,
        "field_label": field_label,
        "field_type": f"{tag}/{field_type}".strip("/") if field_type else tag,
        "role": role,
        "tag": tag,
        "type": field_type,
        "fill_strategy": strategy,
        "value": value,
        "options": [],
    }
    global _resume_path
    if not _resume_path:
        _resume_path = find_resume_pdf()

    try:
        success = _fill_single_field(page, item, _resume_path, max_retries=3)
        if success:
            return {"status": "filled", "field_id": field_id, "field_label": field_label}
        else:
            # Try fallback
            from resume_skill.agent.form_filler import _fill_fallback
            success = _fill_fallback(page, item, value, _resume_path)
            return {
                "status": "filled" if success else "failed",
                "field_id": field_id,
                "field_label": field_label,
                "fallback_used": not success,
            }
    except Exception as e:
        return {"status": "error", "field_id": field_id, "error": str(e)}


@with_timeout(10)
def cmd_get_current_url() -> dict:
    """Get current page URL."""
    try:
        page = _get_page()
        return {"url": page.url}
    except Exception as e:
        return {"url": "", "error": str(e)}


@with_timeout(10)
def cmd_verify_field(
    selector: str = "",
    expected_value: str = "",
    xpath: str = "",
    frame_url: str = "",
    field_label: str = "",
    tag: str = "input",
    field_type: str = "text",
) -> dict:
    page = _get_page()
    item: dict[str, Any] = {
        "selector": selector,
        "xpath": xpath,
        "frame_url": frame_url,
        "field_label": field_label,
        "tag": tag,
        "type": field_type,
    }
    try:
        result = _verify_fill(page, item, expected_value)
        return {"verified": result, "expected": expected_value}
    except Exception as e:
        return {"verified": False, "expected": expected_value, "error": str(e)}


@with_timeout(10)
def cmd_match_fields(fields_json: str, profile_json: str) -> dict:
    """用三阶匹配引擎匹配字段和用户档案（纯计算，不操作浏览器）"""
    try:
        fields = json.loads(fields_json)
        profile = json.loads(profile_json)
        from resume_skill.agent.field_matcher import match_fields_rule_based
        fill_plan = match_fields_rule_based(fields, profile)
        return {"fill_plan": fill_plan, "count": len(fill_plan)}
    except Exception as e:
        return {"error": str(e), "fill_plan": [], "count": 0}


@with_timeout(10)
def cmd_find_and_click(keywords: list[str]) -> dict:
    _get_page()
    for keyword in keywords:
        try:
            clicked = browser.click_by_keywords([keyword])
            if clicked:
                return {"clicked": True, "keyword": keyword}
        except Exception:
            continue
    return {"clicked": False, "matched_keyword": ""}


def cmd_wait_for_user(message: str = "请完成操作后按 Enter 继续...") -> dict:
    input(message)
    return {"status": "continue"}


TOOL_ROUTES = {
    "browser_start": cmd_browser_start,
    "browser_navigate": cmd_browser_navigate,
    "browser_close": cmd_browser_close,
    "get_page_text": cmd_get_page_text,
    "get_current_url": cmd_get_current_url,
    "extract_fields": cmd_extract_fields,
    "match_fields": cmd_match_fields,
    "fill_field": cmd_fill_field,
    "verify_field": cmd_verify_field,
    "find_and_click": cmd_find_and_click,
    "wait_for_user": cmd_wait_for_user,
    "help": lambda: {"tools": {k: v["description"] for k, v in TOOL_HELP.items()}},
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
    main()
