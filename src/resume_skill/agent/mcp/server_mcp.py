"""
MCP Server using official MCP Python SDK (FastMCP).

Requires: mcp>=1.0, Python>=3.10

Usage: python server_mcp.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# 确保能找到项目模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from mcp.server.fastmcp import FastMCP
from resume_skill.agent.browser_agent import BrowserAgent
from resume_skill.agent.form_extractor import extract_fields_rule_based
from resume_skill.agent.form_filler import _fill_single_field, _verify_fill, _resolve_locator
from resume_skill.agent.utils import find_resume_pdf
from resume_skill.agent.field_matcher import match_fields_rule_based

mcp = FastMCP("resume-skill")

browser: BrowserAgent | None = None
_resume_path: str = ""


def _get_page():
    if browser is None:
        raise RuntimeError("Browser not started. Call browser_start first.")
    return browser.page


@mcp.tool(timeout=30)
def browser_start(session_dir: str = ".session/chrome",
                  headless: bool = False,
                  slow_motion: int = 300) -> str:
    """启动浏览器（headless=false，用户可见），返回 JSON 状态"""
    global browser
    if browser is not None:
        return json.dumps({"status": "already_started"}, ensure_ascii=False)
    browser = BrowserAgent(
        session_profile_dir=session_dir,
        keep_browser_open=True,
        headless=headless,
        slow_motion=slow_motion,
    )
    browser.start()
    return json.dumps({"status": "started"}, ensure_ascii=False)


@mcp.tool(timeout=30)
def browser_navigate(url: str) -> str:
    """在浏览器中打开指定 URL"""
    _get_page()
    browser.open_url(url)
    return json.dumps({"status": "navigated", "url": url}, ensure_ascii=False)


@mcp.tool()
def browser_close() -> str:
    """关闭浏览器（清理操作，不设超时）"""
    global browser
    if browser:
        try:
            browser.close()
        except Exception:
            pass  # 忽略关闭过程中的异常
        browser = None
    return json.dumps({"status": "closed"}, ensure_ascii=False)


@mcp.tool(timeout=10)
def get_page_text() -> str:
    """提取当前页面的文本内容（用于 JD 分析）"""
    text = browser.get_page_text()
    return json.dumps({"text": text, "length": len(text)}, ensure_ascii=False)


@mcp.tool(timeout=15)
def extract_fields() -> str:
    """提取当前页面所有表单字段（规则通道）返回原始字段列表，需要后续匹配"""
    page = _get_page()
    fields = extract_fields_rule_based(page)
    return json.dumps({"fields": fields, "count": len(fields)}, ensure_ascii=False)


@mcp.tool(timeout=10)
def get_current_url() -> str:
    """获取当前页面URL"""
    try:
        page = _get_page()
        return json.dumps({"url": page.url}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"url": "", "error": str(e)}, ensure_ascii=False)


@mcp.tool(timeout=10)
def match_fields(fields_json: str, profile_json: str) -> str:
    """用三阶匹配引擎匹配字段和用户档案（纯计算，不操作浏览器）"""
    try:
        fields = json.loads(fields_json)
        profile = json.loads(profile_json)
        fill_plan = match_fields_rule_based(fields, profile)
        return json.dumps({"fill_plan": fill_plan, "count": len(fill_plan)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "fill_plan": [], "count": 0}, ensure_ascii=False)


@mcp.tool(timeout=15)
def fill_field(field_id: str = "",
               selector: str = "",
               value: str = "",
               strategy: str = "text",
               xpath: str = "",
               frame_url: str = "",
               field_label: str = "",
               tag: str = "input",
               field_type: str = "text",
               role: str = "") -> str:
    """填充单个表单字段（九策略自动降级）"""
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
            return json.dumps({"status": "filled", "field_id": field_id, "field_label": field_label}, ensure_ascii=False)
        else:
            # Try fallback
            from resume_skill.agent.form_filler import _fill_fallback
            success = _fill_fallback(page, item, value, _resume_path)
            return json.dumps({
                "status": "filled" if success else "failed",
                "field_id": field_id,
                "field_label": field_label,
                "fallback_used": not success,
            }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "field_id": field_id, "error": str(e)}, ensure_ascii=False)


@mcp.tool(timeout=10)
def verify_field(selector: str = "",
                 expected_value: str = "",
                 xpath: str = "",
                 frame_url: str = "",
                 field_label: str = "",
                 tag: str = "input",
                 field_type: str = "text") -> str:
    """校验单个字段是否填入了期望值"""
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
        return json.dumps({"verified": result, "expected": expected_value}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"verified": False, "expected": expected_value, "error": str(e)}, ensure_ascii=False)


@mcp.tool(timeout=10)
def find_and_click(keywords: list[str]) -> str:
    """根据关键词查找按钮并点击（申请/提交）"""
    _get_page()
    for keyword in keywords:
        try:
            clicked = browser.click_by_keywords([keyword])
            if clicked:
                return json.dumps({"clicked": True, "keyword": keyword}, ensure_ascii=False)
        except Exception:
            continue
    return json.dumps({"clicked": False, "matched_keyword": ""}, ensure_ascii=False)


@mcp.tool()
def wait_for_user(message: str = "请完成操作后按 Enter 继续...") -> str:
    """等待用户手动操作（如登录），用户按下回车后继续"""
    input(message)
    return json.dumps({"status": "continue"}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")