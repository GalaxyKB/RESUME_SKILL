"""
Form filler with multi-strategy fallback and post-fill verification.

Key improvements over v1:
- 4-level selector resolution (CSS → XPath → text → getByRole)
- Radio/checkbox support (no longer skipped)
- Date picker handling
- Cascader support
- Post-fill verification
- Per-field retry with different strategies
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from .utils import find_resume_pdf, timestamp


def fill_form(
    page: Page,
    fill_plan: list[dict[str, Any]],
    resume_path: str = "",
    max_retries: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """Execute fill plan with multi-strategy fallback and verification."""
    if not resume_path:
        resume_path = find_resume_pdf()

    result: dict[str, list[dict[str, Any]]] = {
        "filled": [],
        "skipped": [],
        "failed": [],
        "review": [],
    }

    for item in fill_plan:
        action = item.get("action", "manual")
        if action in ("skip", "manual"):
            result["skipped"].append(item)
            continue

        value = str(item.get("value", "")).strip()
        if not value and item.get("fill_strategy") != "upload":
            result["skipped"].append({**item, "reason": "Empty value"})
            continue

        success = _fill_single_field(page, item, resume_path, max_retries)

        if success:
            verified = _verify_fill(page, item, value)
            if verified:
                result["filled"].append(item)
            else:
                result["review"].append({**item, "reason": "Post-fill verification mismatch"})
        else:
            result["failed"].append({**item, "reason": "All strategies failed"})

    # Take screenshot after filling
    _take_screenshot(page)

    return result


def _fill_single_field(page: Page, item: dict[str, Any], resume_path: str, max_retries: int) -> bool:
    """Try to fill a single field with multiple strategies."""
    strategy = item.get("fill_strategy", "text")
    value = str(item.get("value", ""))

    for attempt in range(max_retries):
        try:
            if strategy == "upload":
                success = _fill_upload(page, item, resume_path)
            elif strategy == "select":
                success = _fill_native_select(page, item, value)
            elif strategy == "custom_select":
                success = _fill_custom_select(page, item, value)
            elif strategy == "radio_click":
                success = _fill_radio(page, item, value)
            elif strategy == "checkbox_click":
                success = _fill_checkbox(page, item, value)
            elif strategy == "datepicker":
                success = _fill_datepicker(page, item, value)
            elif strategy == "cascader":
                success = _fill_cascader(page, item, value)
            elif strategy == "contenteditable":
                success = _fill_contenteditable(page, item, value)
            else:
                success = _fill_text(page, item, value)

            if success:
                return True
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"  Failed to fill {item.get('field_label', '?')}: {e}")

        # Brief pause between retries
        page.wait_for_timeout(300)

    # Fallback: try alternative strategy
    return _fill_fallback(page, item, value, resume_path)


def _resolve_locator(page: Page, item: dict[str, Any]) -> Any:
    """4-level selector resolution: CSS → XPath → getByText → getByRole."""
    frame_url = item.get("frame_url", "")
    context = _resolve_frame(page, frame_url)

    # Level 1: CSS selector
    selector = item.get("selector", "")
    if selector:
        try:
            loc = context.locator(selector).first
            if loc.count() > 0:
                return loc
        except Exception:
            pass

    # Level 2: XPath
    xpath = item.get("xpath", "")
    if xpath:
        try:
            loc = context.locator(f"xpath={xpath}").first
            if loc.count() > 0:
                return loc
        except Exception:
            pass

    # Level 3: getByText (for buttons, labels, etc.)
    label = item.get("field_label", "")
    if label:
        try:
            loc = context.get_by_text(label, exact=False).first
            if loc.count() > 0:
                return loc
        except Exception:
            pass

    # Level 4: getByRole
    role = item.get("role", "")
    if role:
        try:
            loc = context.get_by_role(role, name=label or item.get("placeholder", "")).first
            if loc.count() > 0:
                return loc
        except Exception:
            pass

    return None


def _resolve_frame(page: Page, frame_url: str) -> Any:
    """Enhanced frame resolution with multiple fallback strategies."""
    if not frame_url:
        return page
    
    # Strategy 1: Exact URL match
    for frame in page.frames:
        if frame.url == frame_url:
            return frame
    
    # Strategy 2: URL contains match (for dynamic URLs)
    base_url = frame_url.split('?')[0].split('#')[0]  # Remove query params and fragments
    for frame in page.frames:
        if base_url in frame.url:
            return frame
    
    # Strategy 3: Match by frame name (future enhancement)
    # Note: Frame name/title would need to be stored during field extraction
    # for this to work properly
    
    # Strategy 4: Match by domain
    try:
        from urllib.parse import urlparse
        target_domain = urlparse(frame_url).netloc
        for frame in page.frames:
            if urlparse(frame.url).netloc == target_domain:
                return frame
    except Exception:
        pass
    
    # Fallback to main page
    return page


def _fill_text(page: Page, item: dict[str, Any], value: str) -> bool:
    """Fill a text input with multiple fallback strategies."""
    locator = _resolve_locator(page, item)
    if not locator:
        return False

    # Strategy 1: clear + fill
    try:
        locator.click(timeout=2000)
        locator.clear(timeout=1000)
        locator.fill(value, timeout=3000)
        return True
    except Exception:
        pass

    # Strategy 2: click + select all + type
    try:
        locator.click(timeout=2000)
        page.keyboard.press("Control+a")
        page.keyboard.type(value, delay=30)
        return True
    except Exception:
        pass

    # Strategy 3: Enhanced JS evaluation with comprehensive event dispatching
    try:
        locator.evaluate(
            """(el, val) => {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    // Set value using native setter to bypass React/Vue detection
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    )?.set || Object.getOwnPropertyDescriptor(
                        window.HTMLTextAreaElement.prototype, 'value'
                    )?.set;
                    
                    if (nativeInputValueSetter) {
                        nativeInputValueSetter.call(el, val);
                    } else {
                        el.value = val;
                    }
                    
                    // Dispatch comprehensive events for React/Vue compatibility
                    el.dispatchEvent(new Event('focus', { bubbles: true }));
                    el.dispatchEvent(new InputEvent('beforeinput', { 
                        inputType: 'insertText', 
                        data: val, 
                        bubbles: true 
                    }));
                    el.dispatchEvent(new InputEvent('input', { 
                        inputType: 'insertText', 
                        bubbles: true,
                        cancelable: true
                    }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new Event('blur', { bubbles: true }));
                    
                    // Trigger composition events for CJK input compatibility
                    if (/[\u4e00-\u9fff\u3400-\u4dbf]/.test(val)) {
                        el.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
                        el.dispatchEvent(new CompositionEvent('compositionend', { 
                            data: val, 
                            bubbles: true 
                        }));
                    }
                }
            }""",
            value,
        )
        # Wait for React/Vue to process events
        page.wait_for_timeout(200)
        return True
    except Exception:
        pass

    return False


def _fill_native_select(page: Page, item: dict[str, Any], value: str) -> bool:
    """Fill a native <select> dropdown."""
    locator = _resolve_locator(page, item)
    if not locator:
        return False

    options = item.get("options", [])

    # Try select_option by label
    for opt in options:
        opt_text = str(opt.get("text", "")).strip()
        opt_value = str(opt.get("value", "")).strip()
        if opt_text == value or opt_value == value:
            try:
                locator.select_option(label=opt_text, timeout=3000)
                return True
            except Exception:
                try:
                    locator.select_option(value=opt_value, timeout=3000)
                    return True
                except Exception:
                    pass

    # Try fuzzy match
    for opt in options:
        opt_text = str(opt.get("text", "")).strip()
        if value.lower() in opt_text.lower() or opt_text.lower() in value.lower():
            try:
                locator.select_option(label=opt_text, timeout=3000)
                return True
            except Exception:
                pass

    # Try direct select_option
    try:
        locator.select_option(label=value, timeout=3000)
        return True
    except Exception:
        pass

    return False


def _fill_custom_select(page: Page, item: dict[str, Any], value: str) -> bool:
    """Fill a custom dropdown component (Ant Design, Element Plus, etc.)."""
    locator = _resolve_locator(page, item)
    if not locator:
        return False

    # Strategy 1: Click to open, find option by text
    try:
        locator.click(timeout=2000)
        page.wait_for_timeout(500)

        option_selectors = [
            "[role='option']",
            ".ant-select-item-option",
            ".el-select-dropdown__item",
            ".arco-select-option",
            "li[role='option']",
            ".dropdown-item",
        ]

        for sel in option_selectors:
            try:
                option = page.locator(sel).filter(has_text=value).first
                if option.count() > 0:
                    option.click(timeout=2000)
                    page.wait_for_timeout(200)
                    return True
            except Exception:
                continue

        # Fuzzy match
        for sel in option_selectors:
            try:
                options = page.locator(sel)
                count = options.count()
                for j in range(count):
                    opt = options.nth(j)
                    text = (opt.text_content() or "").strip()
                    if value.lower() in text.lower() or text.lower() in value.lower():
                        opt.click(timeout=1000)
                        page.wait_for_timeout(200)
                        return True
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 2: Type to search + Enter
    try:
        locator.click(timeout=2000)
        page.wait_for_timeout(300)
        page.keyboard.type(value, delay=40)
        page.wait_for_timeout(500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)
        return True
    except Exception:
        pass

    # Strategy 3: Keyboard navigation
    try:
        locator.click(timeout=2000)
        page.wait_for_timeout(300)
        for _ in range(15):
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(100)
            highlighted = page.locator("[role='option'][aria-selected='true'], .ant-select-item-option-active, .el-select-dropdown__item.hover").first
            if highlighted.count() > 0:
                text = (highlighted.text_content() or "").strip()
                if value.lower() in text.lower():
                    page.keyboard.press("Enter")
                    return True
        page.keyboard.press("Escape")
    except Exception:
        pass

    return False


def _fill_radio(page: Page, item: dict[str, Any], value: str) -> bool:
    """Click the matching radio button option."""
    frame_url = item.get("frame_url", "")
    context = _resolve_frame(page, frame_url)

    # Strategy 1: Find radio by label text
    try:
        radio_label = context.locator("label").filter(has_text=value).first
        if radio_label.count() > 0:
            radio_label.click(timeout=2000)
            return True
    except Exception:
        pass

    # Strategy 2: Find radio input by value, then click its label
    name = item.get("name", "")
    if name:
        try:
            radios = context.locator(f'input[type="radio"][name="{name}"]')
            count = radios.count()
            for j in range(count):
                radio = radios.nth(j)
                radio_value = radio.get_attribute("value") or ""
                if radio_value == value or value.lower() in radio_value.lower():
                    # Click the parent label or the radio itself
                    parent_label = radio.locator("xpath=ancestor::label[1]").first
                    if parent_label.count() > 0:
                        parent_label.click(timeout=2000)
                    else:
                        radio.click(timeout=2000)
                    return True
        except Exception:
            pass

    # Strategy 3: Use nearby text to find the right option
    try:
        options = item.get("options", [])
        for opt in options:
            opt_text = str(opt.get("text", "")).strip()
            opt_value = str(opt.get("value", "")).strip()
            if value == opt_text or value == opt_value or value.lower() in opt_text.lower():
                loc = context.get_by_text(opt_text, exact=False).first
                if loc.count() > 0:
                    loc.click(timeout=2000)
                    return True
    except Exception:
        pass

    # Strategy 4: Click the original locator if it's a radio
    locator = _resolve_locator(page, item)
    if locator:
        try:
            locator.click(timeout=2000)
            return True
        except Exception:
            pass

    return False


def _fill_checkbox(page: Page, item: dict[str, Any], value: str) -> bool:
    """Check/uncheck checkbox or select options in a checkbox group."""
    options = item.get("options", [])

    if options and value:
        target_values = [v.strip() for v in value.split(",") if v.strip()]
        frame_url = item.get("frame_url", "")
        context = _resolve_frame(page, frame_url)
        any_clicked = False

        for target in target_values:
            for opt in options:
                opt_text = str(opt.get("text", "")).strip()
                opt_value = str(opt.get("value", "")).strip()
                if target == opt_text or target == opt_value or target.lower() in opt_text.lower():
                    try:
                        loc = context.get_by_text(opt_text, exact=False).first
                        if loc.count() > 0:
                            loc.click(timeout=2000)
                            any_clicked = True
                            break
                    except Exception:
                        pass
                    try:
                        name = item.get("name", "")
                        sel = f'input[type="checkbox"][name="{name}"][value="{opt_value}"]' if name else f'input[type="checkbox"][value="{opt_value}"]'
                        cb = context.locator(sel).first
                        if cb.count() > 0 and not cb.is_checked():
                            cb.click(timeout=2000)
                            any_clicked = True
                            break
                    except Exception:
                        pass
        return any_clicked

    locator = _resolve_locator(page, item)
    if not locator:
        return False

    try:
        is_checked = locator.is_checked()
        should_check = value.lower() in ("true", "yes", "1", "是", "勾选", "同意", "确认")

        if should_check and not is_checked:
            locator.click(timeout=2000)
        elif not should_check and is_checked:
            locator.click(timeout=2000)
        return True
    except Exception:
        try:
            frame_url = item.get("frame_url", "")
            context = _resolve_frame(page, frame_url)
            label_text = item.get("field_label", "")
            if label_text:
                label = context.locator("label").filter(has_text=label_text).first
                if label.count() > 0:
                    label.click(timeout=2000)
                    return True
        except Exception:
            pass
        return False


def _fill_datepicker(page: Page, item: dict[str, Any], value: str) -> bool:
    """Fill a date picker with multiple strategies."""
    locator = _resolve_locator(page, item)
    if not locator:
        return False

    # Strategy 1: Direct fill (works for native date inputs)
    try:
        locator.click(timeout=2000)
        locator.fill(value, timeout=2000)
        page.keyboard.press("Enter")
        return True
    except Exception:
        pass

    # Strategy 2: Type the date
    try:
        locator.click(timeout=2000)
        page.keyboard.press("Control+a")
        page.keyboard.type(value, delay=40)
        page.keyboard.press("Enter")
        return True
    except Exception:
        pass

    # Strategy 3: Clear first, then type
    try:
        locator.click(timeout=2000)
        locator.clear(timeout=1000)
        page.keyboard.type(value, delay=40)
        page.keyboard.press("Tab")
        return True
    except Exception:
        pass

    return False


def _fill_cascader(page: Page, item: dict[str, Any], value: str) -> bool:
    """Fill a cascader (province/city/district) by clicking through levels."""
    locator = _resolve_locator(page, item)
    if not locator:
        return False

    if "/" in value:
        levels = [v.strip() for v in value.split("/") if v.strip()]
    else:
        levels = [v.strip() for v in value.split() if v.strip()]
    if not levels:
        levels = [value]

    try:
        # Click to open cascader
        locator.click(timeout=2000)
        page.wait_for_timeout(500)

        for level_value in levels:
            # Find and click the option
            option_selectors = [
                "[role='option']",
                ".ant-cascader-menu-item",
                ".el-cascader-node",
                ".arco-cascader-option",
                ".cascader-menu-item",
            ]

            clicked = False
            for sel in option_selectors:
                try:
                    option = page.locator(sel).filter(has_text=level_value).first
                    if option.count() > 0:
                        option.click(timeout=2000)
                        page.wait_for_timeout(500)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                # Try typing to filter
                page.keyboard.type(level_value, delay=30)
                page.wait_for_timeout(300)
                page.keyboard.press("Enter")
                page.wait_for_timeout(500)

    except Exception:
        return False

    return True


def _fill_contenteditable(page: Page, item: dict[str, Any], value: str) -> bool:
    """Fill a contenteditable element."""
    locator = _resolve_locator(page, item)
    if not locator:
        return False

    # Strategy 1: Click + type
    try:
        locator.click(timeout=2000)
        page.keyboard.press("Control+a")
        page.keyboard.type(value, delay=20)
        return True
    except Exception:
        pass

    # Strategy 2: JS evaluation
    try:
        locator.evaluate(
            """(el, val) => {
                el.focus();
                el.innerText = val;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            }""",
            value,
        )
        return True
    except Exception:
        pass

    # Strategy 3: innerHTML for rich text
    try:
        locator.evaluate(
            """(el, val) => {
                el.innerHTML = '<p>' + val + '</p>';
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }""",
            value,
        )
        return True
    except Exception:
        pass

    return False


def _fill_upload(page: Page, item: dict[str, Any], resume_path: str) -> bool:
    """Upload a file (resume PDF)."""
    if not resume_path or not resume_path.strip() or not Path(resume_path).exists():
        print(f"  Upload skipped: file not found ({resume_path})")
        return False

    frame_url = item.get("frame_url", "")
    context = _resolve_frame(page, frame_url)

    # Strategy 1: Direct set_input_files on visible file input
    locator = _resolve_locator(page, item)
    if locator:
        try:
            locator.set_input_files(resume_path)
            print(f"  Uploaded: {item.get('field_label', 'file')}")
            return True
        except Exception:
            pass

    # Strategy 2: Find hidden file input
    try:
        file_inputs = context.locator("input[type='file']")
        count = file_inputs.count()
        for j in range(count):
            fi = file_inputs.nth(j)
            try:
                fi.set_input_files(resume_path)
                print(f"  Uploaded via hidden input")
                return True
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 3: Click upload button, then find file input
    if locator:
        try:
            locator.click(timeout=2000)
            page.wait_for_timeout(1000)
            file_inputs = context.locator("input[type='file']")
            if file_inputs.count() > 0:
                file_inputs.first.set_input_files(resume_path)
                print(f"  Uploaded after clicking button")
                return True
        except Exception:
            pass

    return False


def _fill_fallback(page: Page, item: dict[str, Any], value: str, resume_path: str) -> bool:
    """Last-resort fallback: try text strategy for non-text fields."""
    strategy = item.get("fill_strategy", "text")

    if strategy != "text" and value:
        try:
            return _fill_text(page, item, value)
        except Exception:
            pass

    return False


def _verify_fill(page: Page, item: dict[str, Any], expected_value: str) -> bool:
    """Enhanced verification that the field was actually filled with the expected value."""
    locator = _resolve_locator(page, item)
    if not locator:
        return True  # Can't verify, assume success

    try:
        tag = str(item.get("tag", "")).lower()
        ftype = str(item.get("type", "")).lower()
        
        # Store original value before comparison for debugging
        original_value = None
        try:
            original_value = locator.evaluate("el => el.value || el.textContent || ''")
        except Exception:
            pass

        if tag == "select":
            # Check selected option text and value
            selected_text = locator.evaluate("el => el.options[el.selectedIndex]?.textContent || ''")
            selected_value = locator.evaluate("el => el.options[el.selectedIndex]?.value || ''")
            is_match = (expected_value.lower() in selected_text.lower() or 
                       expected_value.lower() in selected_value.lower())
            if not is_match:
                print(f"  ⚠️ Select verification failed: expected '{expected_value}', got text='{selected_text}', value='{selected_value}'")
            return is_match
        elif ftype in ("radio", "checkbox"):
            # Check if the correct option is selected
            is_checked = locator.evaluate("el => el.checked")
            if ftype == "radio":
                # For radio, verify the selected value matches expected
                radio_value = locator.evaluate("el => el.value || ''")
                is_match = is_checked and (expected_value.lower() in radio_value.lower() or radio_value.lower() in expected_value.lower())
                if not is_match:
                    print(f"  ⚠️ Radio verification failed: expected '{expected_value}', got checked={is_checked}, value='{radio_value}'")
                return is_match
            return is_checked  # For checkbox, just check if it's checked
        elif "file" in ftype:
            # Check if file input has files
            file_count = locator.evaluate("el => el.files ? el.files.length : 0")
            return file_count > 0
        else:
            # Enhanced text field verification
            actual = locator.evaluate("el => el.value || el.textContent || ''")
            if not actual.strip():
                print(f"  ⚠️ Text verification failed: field is empty, expected '{expected_value}'")
                return False
            
            # Strict verification for exact matches
            if actual.strip() == expected_value.strip():
                return True
                
            # Looser verification for partial matches (with length check)
            is_partial_match = (expected_value.lower() in actual.lower() or 
                              actual.lower() in expected_value.lower())
            
            # Additional check: ensure the field hasn't been filled with wrong content
            # If actual value is very different from expected (e.g., different field entirely)
            if len(actual) > 10 and len(expected_value) > 10:
                # Calculate improved similarity using Levenshtein-like approach
                def calculate_similarity(s1: str, s2: str) -> float:
                    """Calculate text similarity using multiple metrics."""
                    s1, s2 = s1.lower().strip(), s2.lower().strip()
                    if not s1 or not s2:
                        return 0.0
                    if s1 == s2:
                        return 1.0
                    
                    # Check if one is contained in the other
                    if s1 in s2 or s2 in s1:
                        return 0.8
                    
                    # Character overlap similarity
                    chars1, chars2 = set(s1), set(s2)
                    char_overlap = len(chars1 & chars2) / len(chars1 | chars2)
                    
                    # Word overlap similarity (for longer texts)
                    if len(s1) > 5 and len(s2) > 5:
                        words1 = set(s1.split())
                        words2 = set(s2.split())
                        if words1 and words2:
                            word_overlap = len(words1 & words2) / len(words1 | words2)
                            return max(char_overlap, word_overlap)
                    
                    return char_overlap
                
                similarity = calculate_similarity(actual, expected_value)
                if similarity < 0.3:
                    print(f"  ⚠️ Text verification failed: low similarity. Expected '{expected_value}', got '{actual}'")
                    return False
            
            if not is_partial_match:
                print(f"  ⚠️ Text verification failed: expected '{expected_value}', got '{actual}'")
                
            return is_partial_match
    except Exception as e:
        print(f"  ⚠️ Verification error: {e}")
        return True  # Can't verify, assume success


def _take_screenshot(page: Page) -> str:
    """Take a screenshot after filling."""
    from ..config import CONFIG
    from .utils import ensure_dirs
    ensure_dirs()
    screenshot_dir = CONFIG.outputs_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    path = screenshot_dir / f"{timestamp()}_after_fill.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass
    return str(path)
