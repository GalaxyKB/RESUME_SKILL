from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from .config import OUTPUTS_DIR, PROJECT_ROOT
from .storage import ensure_dirs
from .utils import safe_filename, timestamp


def _resolve_resume_pdf_path(resume_path: str) -> str:
    candidates = [
        Path(resume_path),
        PROJECT_ROOT / resume_path,
        PROJECT_ROOT / "data" / "resume.pdf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    pdf_candidates = sorted(PROJECT_ROOT.glob("*.pdf"))
    if pdf_candidates:
        return str(pdf_candidates[0])
    return resume_path


def _field_text(plan_item: dict[str, Any]) -> str:
    parts = [
        plan_item.get("field_label", ""),
        plan_item.get("field_type", ""),
        plan_item.get("selector", ""),
        plan_item.get("xpath", ""),
    ]
    return " ".join(str(part) for part in parts if part)


def _resolve_context(page: Page, frame_url: str) -> Any:
    if not frame_url:
        return page
    for frame in page.frames:
        if frame.url == frame_url:
            return frame
    return page


def _resolve_locator(context: Any, selector: str, xpath: str) -> Any:
    if selector:
        try:
            return context.locator(selector).first
        except Exception:
            pass
    if xpath:
        try:
            return context.locator(f"xpath={xpath}").first
        except Exception:
            pass
    raise ValueError("No valid selector or xpath for locator")


def _choose_dropdown_option(page: Page, locator: Any, value: str) -> bool:
    """
    Try to select an option from a dropdown/combobox with multiple strategy fallbacks.
    Strategies:
    1. Find option by exact text match (multiple selectors)
    2. If option not found, try keyboard navigation
    3. If still not found, try typing value and pressing Enter
    """
    target = str(value).strip()
    if not target:
        return False
    
    try:
        # First, make sure dropdown is visible and clickable
        locator.click(timeout=1000)
        page.wait_for_timeout(300)  # Wait for dropdown animation
    except Exception:
        return False
    
    # Strategy 1: Search for option element in multiple possible containers
    option_selectors = [
        "[role='option']",
        ".ant-select-item-option",
        ".ant-select-item-option-content",
        ".arco-select-option",
        ".el-select-dropdown__item",
        "li[role='option']",
        "div[role='option']",
        ".dropdown-item",
        "[role='menuitem']",
    ]
    
    for selector in option_selectors:
        try:
            # Look for option containing target text
            option_locator = page.locator(selector).filter(has_text=target).first
            count = option_locator.count()
            if count > 0:
                try:
                    option_locator.click(timeout=800)
                    page.wait_for_timeout(200)  # Wait for selection effect
                    return True
                except Exception:
                    continue
        except Exception:
            continue
    
    # Strategy 2: Keyboard navigation - try arrow keys + Enter
    try:
        for _ in range(10):  # Assume max 10 options
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(100)
            # Try to find highlighted/selected option with matching text
            highlighted = page.locator("[role='option'][aria-selected='true']").first
            if highlighted.count() > 0:
                text = highlighted.text_content() or ""
                if target.lower() in text.lower():
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(200)
                    return True
    except Exception:
        pass
    
    # Strategy 3: Try typing value directly
    try:
        page.keyboard.type(target, delay=50)
        page.wait_for_timeout(200)
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        return True
    except Exception:
        pass
    
    return False


def fill_form(page: Page, fill_plan: list[dict[str, Any]], resume_path: str = "data/resume.pdf", allow_review_then_fill: bool = False) -> dict[str, list[dict[str, Any]]]:
    ensure_dirs()
    resume_pdf_path = _resolve_resume_pdf_path(resume_path)
    result: dict[str, list[dict[str, Any]]] = {"filled": [], "skipped": [], "failed": []}

    for item in fill_plan:
        action = item.get("action", "user_manual")
        selector = item.get("selector", "")
        xpath = str(item.get("xpath", "") or "")
        frame_url = str(item.get("frame_url", "") or "")
        value = item.get("value", "")
        field_text = _field_text(item)
        field_type = str(item.get("field_type", "")).lower()
        role = str(item.get("role", "")).lower()

        if action == "skip" or action == "user_manual":
            result["skipped"].append(item)
            continue
        if action == "review_then_fill" and not allow_review_then_fill:
            result["skipped"].append(item)
            continue
        if not selector and not xpath:
            result["failed"].append({**item, "error": "Missing selector"})
            continue

        try:
            context = _resolve_context(page, frame_url)
            locator = _resolve_locator(context, selector, xpath)
            if not str(value).strip() and action != "user_manual":
                result["skipped"].append({**item, "reason": "Missing explicit value"})
                continue
            if "file" in field_type:
                locator.set_input_files(resume_pdf_path)
            elif "upload" in field_text.lower() and ("button" in field_type or role == "button"):
                # Some sites expose upload as a button while file input is hidden.
                file_input = context.locator("input[type='file']").first
                file_input.set_input_files(resume_pdf_path)
            elif "select" in field_type:
                options = locator.evaluate(
                    """
                    (el) => Array.from(el.options || []).map(option => ({text: option.textContent.trim(), value: option.value}))
                    """
                )
                selected = False
                for option in options:
                    if str(value).strip() and (str(option.get("text", "")).strip() == str(value).strip() or str(option.get("value", "")).strip() == str(value).strip()):
                        locator.select_option(label=option.get("text", ""))
                        selected = True
                        break
                if not selected:
                    result["skipped"].append({**item, "reason": "No matching select option"})
                    continue
            elif "combobox" in field_type or role == "combobox":
                # Try dropdown selection with multiple strategies
                try:
                    if _choose_dropdown_option(page, locator, str(value)):
                        result["filled"].append(item)
                        continue
                except Exception as e:
                    pass
                
                # Fallback: try direct input and keyboard
                try:
                    locator.click(timeout=800)
                    page.wait_for_timeout(200)
                    locator.fill(str(value), timeout=800)
                    page.wait_for_timeout(200)
                    page.keyboard.press("Enter")
                    result["filled"].append(item)
                except Exception:
                    result["failed"].append({**item, "reason": "Combobox selection failed", "field_text": field_text})
            elif any(k in field_text for k in ["出生", "日期", "date", "年月"]):
                locator.click()
                try:
                    locator.fill(str(value))
                except Exception:
                    page.keyboard.type(str(value))
                page.keyboard.press("Enter")
            elif "textbox" in field_type or role == "textbox" or "contenteditable" in field_type:
                locator.click()
                try:
                    locator.fill(str(value))
                except Exception:
                    locator.evaluate(
                        """
                        (el, val) => {
                            if (el && el.isContentEditable) {
                                el.innerText = String(val);
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                                el.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }
                        """,
                        str(value),
                    )
            elif "checkbox" in field_type or "radio" in field_type or "password" in field_type or "hidden" in field_type:
                result["skipped"].append(item)
                continue
            else:
                locator.fill(str(value))
            result["filled"].append(item)
        except Exception as exc:
            result["failed"].append({**item, "error": str(exc), "field_text": field_text})

    screenshot_dir = OUTPUTS_DIR / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"{timestamp()}_after_fill.png"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        pass
    result["screenshot_path"] = [
        {
            "path": str(screenshot_path),
        }
    ]
    return result
