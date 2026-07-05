"""
Dual-channel form field extractor.

Channel A: Rule-based extraction (fast, comprehensive)
Channel B: AI HTML analysis (accurate, semantic)

Results are merged with deduplication, preferring AI results.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page

from .utils import print_section


RULE_BASED_SCRIPT = r'''
() => {
  // CSS.escape polyfill for compatibility
  function cssEscape(value) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
    return value.replace(/[!"#$%&'()*+,.\/:;<=>?@[\\\]^`{|}~]/g, '\\$&');
  }

  const isVisible = (el) => {
    if (!el || !el.parentElement) return false;
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style
      && style.display !== 'none'
      && style.visibility !== 'hidden'
      && style.opacity !== '0'
      && rect.width > 0
      && rect.height > 0;
  };

  const inputSelectors = [
    'input[type="text"]:not([readonly]):not([disabled])',
    'input[type="email"]:not([readonly]):not([disabled])',
    'input[type="tel"]:not([readonly]):not([disabled])',
    'input[type="number"]:not([readonly]):not([disabled])',
    'input[type="date"]:not([readonly]):not([disabled])',
    'input[type="month"]:not([readonly]):not([disabled])',
    'input[type="password"]:not([readonly]):not([disabled])',
    'input[type="search"]:not([readonly]):not([disabled])',
    'input[type="url"]:not([readonly]):not([disabled])',
    'input[type="file"]:not([disabled])',
    'input:not([type]):not([readonly]):not([disabled])',
    'textarea:not([readonly]):not([disabled])',
    'select:not([disabled])',
    '[role="combobox"]:not([disabled])',
    '[role="textbox"]:not([readonly]):not([disabled])',
    '[role="searchbox"]:not([readonly]):not([disabled])',
    '[contenteditable="true"]',
    'input[type="radio"]:not([disabled])',
    'input[type="checkbox"]:not([disabled])',
  ];

  const fields = [];
  let counter = 1;
  const seenElements = new WeakSet();

  for (const selector of inputSelectors) {
    const elements = document.querySelectorAll(selector);

    for (const el of elements) {
      if (seenElements.has(el)) continue;
      
      // Include both visible and hidden fields (for multi-tab forms)
      const visible = isVisible(el);
      seenElements.add(el);

      const fieldInfo = extractFieldContext(el);

      const tag = (el.tagName || '').toLowerCase();
      const inputType = (el.getAttribute('type') || '').toLowerCase();
      const fieldId = `field_${counter.toString().padStart(3, '0')}`;

      fields.push({
        field_id: fieldId,
        selector: generateSelector(el),
        xpath: generateXPath(el),
        tag: tag,
        type: inputType || tag,
        role: el.getAttribute('role') || '',
        field_label: fieldInfo.label,
        placeholder: el.placeholder || el.getAttribute('placeholder') || '',
        name: el.name || el.getAttribute('name') || '',
        id: el.id || '',
        aria_label: el.getAttribute('aria-label') || '',
        title: el.getAttribute('title') || '',
        data_field: el.getAttribute('data-field') || el.getAttribute('data-name') || '',
        context_text: fieldInfo.context,
        nearby_text: fieldInfo.nearby,
        options: fieldInfo.options,
        required: el.required || el.getAttribute('required') !== null || el.getAttribute('aria-required') === 'true',
        radio_group: (inputType === 'radio') ? (el.name || el.getAttribute('data-group') || '') : '',
        radio_value: (inputType === 'radio') ? el.value : '',
        checked: (inputType === 'radio' || inputType === 'checkbox') ? el.checked : undefined,
        visible: visible,  // Track visibility for debugging
        bounding_rect: {
          x: Math.round(el.getBoundingClientRect().x),
          y: Math.round(el.getBoundingClientRect().y),
          w: Math.round(el.getBoundingClientRect().width),
          h: Math.round(el.getBoundingClientRect().height),
        },
      });

      counter++;
    }
  }

  // Also collect visible labels that aren't associated with inputs (may be for custom components)
  const labelElements = document.querySelectorAll('label, .form-label, .ant-form-item-label, .el-form-item__label, .arco-form-item-label');
  for (const labelEl of labelElements) {
    if (seenElements.has(labelEl)) continue;
    const text = (labelEl.textContent || '').trim();
    if (!text || text.length > 100) continue;

    // Check if this label's for-attribute points to an already-collected field
    const forAttr = labelEl.getAttribute('for');
    if (forAttr) {
      const target = document.getElementById(forAttr);
      if (target && seenElements.has(target)) continue;
    }

    // Check if it contains an already-collected input
    const containedInput = labelEl.querySelector('input, textarea, select');
    if (containedInput && seenElements.has(containedInput)) continue;
  }

  function extractFieldContext(el) {
    let label = '';
    let placeholder = el.placeholder || el.getAttribute('placeholder') || '';
    let context = '';
    let nearby = '';
    let options = [];

    // Strategy 1: label[for] association
    const id = el.id;
    if (id) {
      const labelEl = document.querySelector(`label[for="${cssEscape(id)}"]`);
      if (labelEl) {
        label = (labelEl.textContent || '').trim();
      }
    }

    // Strategy 2: Parent label wrapper
    if (!label) {
      const closestLabel = el.closest('label');
      if (closestLabel) {
        label = (closestLabel.textContent || '').replace(el.value || '', '').trim();
        if (label.length > 80) label = label.substring(0, 80);
      }
    }

    // Strategy 3: aria-label
    if (!label) {
      label = el.getAttribute('aria-label') || '';
    }

    // Strategy 4: aria-labelledby
    if (!label) {
      const labelledBy = el.getAttribute('aria-labelledby');
      if (labelledBy) {
        const labelEl = document.getElementById(labelledBy);
        if (labelEl) {
          label = (labelEl.textContent || '').trim();
        }
      }
    }

    // Strategy 5: title attribute
    if (!label) {
      label = el.getAttribute('title') || '';
    }

    // Strategy 6: Form item container label (Ant Design, Element, Arco, etc.)
    if (!label) {
      const formItem = el.closest('.ant-form-item, .el-form-item, .arco-form-item, .form-group, .form-item, .field-item, [class*="form-item"], [class*="FormItem"]');
      if (formItem) {
        const labelSelectors = [
          '.ant-form-item-label', '.el-form-item__label', '.arco-form-item-label',
          '.form-label', 'label', '.field-label', '[class*="label"]',
          '[class*="Label"]', '.ant-form-item-label-left'
        ];
        for (const sel of labelSelectors) {
          const labelEl = formItem.querySelector(sel);
          if (labelEl) {
            const text = (labelEl.textContent || '').trim();
            if (text && text.length < 80) {
              label = text;
              break;
            }
          }
        }
      }
    }

    // Strategy 7: Walk up the DOM to find label text (up to 6 levels)
    if (!label) {
      let parent = el.parentElement;
      let attempts = 0;
      while (parent && attempts < 6) {
        // Look for sibling elements that look like labels
        for (const sibling of parent.children) {
          if (sibling === el || sibling.contains(el)) continue;
          const text = (sibling.textContent || '').trim();
          if (text && text.length > 1 && text.length < 80) {
            // Check if this text appears label-like
            const isLabelLike = /^[\u4e00-\u9fff\w\s\-/：:()（）]+$/.test(text)
              && !text.includes('\n\n')
              && text.length < 60;
            if (isLabelLike) {
              label = text;
              break;
            }
          }
        }
        if (label) break;
        parent = parent.parentElement;
        attempts++;
      }
    }

    // Strategy 8: Previous sibling text node
    if (!label) {
      const prev = el.previousElementSibling;
      if (prev) {
        const text = (prev.textContent || '').trim();
        if (text && text.length < 60 && text.length > 0) {
          label = text;
        }
      }
    }

    // Collect dropdown options
    const tag = (el.tagName || '').toLowerCase();
    if (tag === 'select') {
      for (const option of el.options) {
        if (option.value && option.textContent.trim()) {
          options.push({ text: option.textContent.trim(), value: option.value });
        }
      }
    }

    // Collect radio group options
    const inputType = (el.getAttribute('type') || '').toLowerCase();
    if (inputType === 'radio' && el.name) {
      const radios = document.querySelectorAll(`input[name="${cssEscape(el.name)}"]`);
      for (const radio of radios) {
        // Find the label for this radio
        let radioLabel = '';
        const radioParent = radio.closest('label');
        if (radioParent) {
          radioLabel = (radioParent.textContent || '').trim();
        }
        if (!radioLabel) {
          const radioId = radio.id;
          if (radioId) {
            const labelEl = document.querySelector(`label[for="${cssEscape(radioId)}"]`);
            if (labelEl) radioLabel = (labelEl.textContent || '').trim();
          }
        }
        options.push({ text: radioLabel || radio.value, value: radio.value });
      }
    }

    // Collect context
    const contextEl = el.closest('.form-group, .form-item, .ant-form-item, .el-form-item, .arco-form-item, [class*="form-item"]');
    if (contextEl) {
      context = (contextEl.textContent || '').slice(0, 400).trim();
    }

    // Collect nearby text
    const nearbyEl = el.parentElement;
    if (nearbyEl) {
      nearby = (nearbyEl.textContent || '').slice(0, 300).trim();
    }

    return { label, placeholder, context, nearby, options };
  }

  function generateSelector(el) {
    // Priority 1: Stable attributes (name, id, data-*)
    if (el.name && el.name.trim()) {
      return `${el.tagName.toLowerCase()}[name="${el.name}"]`;
    }
    if (el.id && el.id.trim()) {
      return `#${cssEscape(el.id)}`;
    }
    
    // Priority 2: Data attributes
    const dataField = el.getAttribute('data-field') || el.getAttribute('data-name') || el.getAttribute('data-testid');
    if (dataField) {
      return `[data-field="${cssEscape(dataField)}"], [data-name="${cssEscape(dataField)}"], [data-testid="${cssEscape(dataField)}"]`;
    }
    
    // Priority 3: ARIA label
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.length < 50) {
      return `[aria-label="${cssEscape(ariaLabel)}"]`;
    }
    
    // Priority 4: Unique class combinations
    if (el.className && typeof el.className === 'string') {
      const classes = el.className.split(/\s+/).filter(c => 
        c.trim() && 
        c.length < 25 && 
        !c.startsWith('_') && 
        !c.includes('--') &&
        !c.match(/^(css-|sc-|emotion-)/)  // Exclude generated classes
      );
      if (classes.length > 0) {
        const classSelector = `.${classes.map(c => cssEscape(c)).join('.')}`;
        // Check if this class combo is unique
        try {
          if (document.querySelectorAll(classSelector).length === 1) {
            return classSelector;
          }
        } catch (e) {}
      }
    }

    // Fallback: Build hierarchical path with stable identifiers
    let parts = [];
    let current = el;
    let depth = 0;

    while (current && current !== document.body && depth < 4) {
      let part = current.tagName.toLowerCase();

      if (current.id) {
        parts.unshift(`#${cssEscape(current.id)}`);
        break;
      }

      if (current.className && typeof current.className === 'string') {
        const classes = current.className.split(/\s+/).filter(c =>
          c.trim() && c.length < 25 && !c.startsWith('_') && !c.includes('--')
        );
        if (classes.length > 0) {
          part += `.${cssEscape(classes[0])}`;
        }
      }

      // Only use nth-of-type as last resort
      const parent = current.parentElement;
      if (parent && depth === 0) {
        const siblings = Array.from(parent.children).filter(s => s.tagName === current.tagName);
        if (siblings.length > 1) {
          const idx = siblings.indexOf(current) + 1;
          part += `:nth-of-type(${idx})`;
        }
      }

      parts.unshift(part);
      current = current.parentElement;
      depth++;
    }

    return parts.join(' > ');
  }

  function generateXPath(el) {
    if (el.id) return `//*[@id="${el.id}"]`;

    const parts = [];
    let current = el;
    while (current && current.nodeType === 1) {
      let index = 1;
      let sibling = current.previousElementSibling;
      while (sibling) {
        if (sibling.tagName === current.tagName) index++;
        sibling = sibling.previousElementSibling;
      }
      parts.unshift(`${current.tagName.toLowerCase()}[${index}]`);
      current = current.parentElement;
    }
    return '/' + parts.join('/');
  }

  return fields;
}
'''


def extract_fields_rule_based(page: Page) -> list[dict[str, Any]]:
    """Channel A: Fast rule-based extraction from all frames."""
    aggregated: list[dict[str, Any]] = []
    dedupe: set[tuple[str, str]] = set()
    counter = 1

    for frame in page.frames:
        try:
            items = frame.evaluate(RULE_BASED_SCRIPT)
        except Exception as e:
            print(f"Warning: Failed to extract from frame {frame.url}: {e}")
            continue
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            item = dict(item)
            selector = str(item.get("selector", ""))
            xpath = str(item.get("xpath", ""))
            sig = (selector, xpath)
            if sig in dedupe:
                continue
            dedupe.add(sig)
            item["field_id"] = f"field_{str(counter).zfill(3)}"
            item["frame_url"] = frame.url
            item["frame_name"] = frame.name or ""
            item["frame_title"] = frame.title or ""
            aggregated.append(item)
            counter += 1

    print(f"[Rule-based] Extracted {len(aggregated)} form fields")
    return aggregated


def extract_fields_ai(page: Page, profile: dict[str, Any], llm_client: Any) -> dict[str, Any]:
    """Channel B: AI-based HTML analysis for accurate semantic matching."""
    form_html = _extract_form_html(page)
    if not form_html:
        return {"error": "No HTML content extracted"}

    cleaned_html = _clean_html(form_html)
    prompt = _build_ai_extraction_prompt(cleaned_html, profile)

    try:
        result = llm_client.call_json("", prompt)
        if isinstance(result, dict) and "fields" in result:
            return result
        return {"error": "Invalid AI response", "raw": result}
    except Exception as e:
        print(f"AI extraction failed: {e}")
        return {"error": str(e)}


def merge_extraction_results(
    rule_fields: list[dict[str, Any]],
    ai_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Merge rule-based and AI results.

    Strategy: Use rule-based as the backbone (guaranteed to have valid
    selectors), then overlay AI semantic info (matched_data, fill_strategy,
    etc.) onto matching fields.  Any AI-only fields are appended at the end.
    
    Also merges radio/checkbox groups to avoid duplicates.
    """
    # First pass: merge radio/checkbox groups
    rule_fields = _merge_radio_checkbox_groups(rule_fields)
    
    ai_fields = _index_ai_fields(ai_result)
    rule_by_selector: dict[str, dict[str, Any]] = {}
    for f in rule_fields:
        sel = f.get("selector", "")
        xp = f.get("xpath", "")
        if sel:
            rule_by_selector[sel] = f
        if xp:
            rule_by_selector[xp] = f

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Pass 1: Walk rule-based fields (backbone), enrich with AI data
    for rule_field in rule_fields:
        field = dict(rule_field)
        field["source"] = "rule"
        sel = field.get("selector", "")
        xp = field.get("xpath", "")

        # Find matching AI field
        ai_match = _find_ai_match(ai_fields, sel, xp, field.get("id", ""), field.get("name", ""))
        if ai_match:
            # Overlay AI semantic info onto the rule-based field
            if ai_match.get("field_name") and not field.get("field_label"):
                field["field_label"] = ai_match["field_name"]
            if ai_match.get("fill_strategy"):
                field["fill_strategy"] = ai_match["fill_strategy"]
            if ai_match.get("fill_action"):
                field["fill_action"] = ai_match["fill_action"]
            matched = ai_match.get("matched_data", {})
            if matched and matched.get("value"):
                field["matched_data"] = matched
                field["ai_value"] = matched["value"]
                field["ai_confidence"] = matched.get("confidence", 0.0)
                field["ai_source"] = matched.get("source", "")
                field["ai_reason"] = matched.get("reason", "")
            if ai_match.get("options"):
                field["ai_options"] = ai_match["options"]
            field["source"] = "rule+ai"

        key = sel or xp or field.get("field_id", "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged.append(field)

    # Pass 2: Add AI-only fields not found in rule-based results
    for ai_key, ai_field in ai_fields.items():
        ai_sel = ai_field.get("selector", "")
        ai_xp = ai_field.get("xpath", "")
        if ai_sel in seen or ai_xp in seen:
            continue
        # Check if this AI field's selector/xpath matches any rule field
        found = False
        for rule_field in rule_fields:
            if _selectors_match(ai_sel, ai_xp, rule_field.get("selector", ""), rule_field.get("xpath", "")):
                found = True
                break
        if found:
            continue

        field = dict(ai_field)
        field["source"] = "ai"
        field["field_id"] = f"field_{str(len(merged) + 1).zfill(3)}"
        if ai_sel:
            seen.add(ai_sel)
        if ai_xp:
            seen.add(ai_xp)
        merged.append(field)

    ai_count = sum(1 for f in merged if "ai" in f.get("source", ""))
    print(f"[Merged] Total: {len(merged)} fields (with AI enrichment: {ai_count}, rule-only: {len(merged) - ai_count})")
    return merged


def _merge_radio_checkbox_groups(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge radio buttons and checkboxes with same name into grouped fields."""
    groups: dict[str, list[dict[str, Any]]] = {}
    non_grouped: list[dict[str, Any]] = []
    
    for field in fields:
        field_type = field.get("field_type", "")
        name = field.get("name", "")
        radio_group = field.get("radio_group", "")
        
        # Group radio buttons by name or radio_group
        if "radio" in field_type and (name or radio_group):
            group_key = f"radio_{radio_group or name}"
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(field)
        # Group checkboxes by name if they share the same name
        elif "checkbox" in field_type and name:
            group_key = f"checkbox_{name}"
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(field)
        else:
            non_grouped.append(field)
    
    # Merge groups into single fields with options
    merged = non_grouped.copy()
    for group_key, group_fields in groups.items():
        if len(group_fields) <= 1:
            merged.extend(group_fields)
            continue
            
        # Create merged field from first field in group
        base_field = group_fields[0].copy()
        options = []
        
        for field in group_fields:
            option = {
                "value": field.get("value", ""),
                "label": field.get("field_label", ""),
                "selector": field.get("selector", ""),
                "xpath": field.get("xpath", ""),
            }
            options.append(option)
        
        base_field["options"] = options
        base_field["field_label"] = f"{base_field.get('field_label', '')} (group)"
        merged.append(base_field)
    
    return merged


def _index_ai_fields(ai_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index AI analysis fields by selector/xpath for fast lookup."""
    indexed: dict[str, dict[str, Any]] = {}
    if "fields" not in ai_result or not isinstance(ai_result["fields"], list):
        return indexed
    for f in ai_result["fields"]:
        if not isinstance(f, dict):
            continue
        sel = f.get("selector", "")
        xp = f.get("xpath", "")
        fid = f.get("field_id", "")
        if sel:
            indexed[sel] = f
        if xp:
            indexed[xp] = f
        if fid:
            indexed[fid] = f
    return indexed


def _find_ai_match(
    ai_fields: dict[str, dict[str, Any]],
    selector: str,
    xpath: str,
    elem_id: str,
    elem_name: str,
) -> dict[str, Any] | None:
    """Find the best-matching AI field for a rule-based field."""
    # Direct match by selector
    if selector and selector in ai_fields:
        return ai_fields[selector]
    # Direct match by xpath
    if xpath and xpath in ai_fields:
        return ai_fields[xpath]
    # Match by id-based selector (#id)
    if elem_id:
        id_sel = f"#{elem_id}"
        if id_sel in ai_fields:
            return ai_fields[id_sel]
    # Match by name-based selector
    if elem_name:
        name_sel = f'[name="{elem_name}"]'
        for key, ai_f in ai_fields.items():
            if name_sel in key:
                return ai_f
    # Fuzzy match
    for key, ai_f in ai_fields.items():
        if _selectors_match(selector, xpath, ai_f.get("selector", ""), ai_f.get("xpath", "")):
            return ai_f
    return None


def _selectors_match(sel1: str, xp1: str, sel2: str, xp2: str) -> bool:
    """Check if two selector pairs refer to the same element."""
    if sel1 and sel2 and (sel1 == sel2 or sel1 in sel2 or sel2 in sel1):
        return True
    if xp1 and xp2 and xp1 == xp2:
        return True
    return False


def extract_form_fields(page: Page, profile: dict[str, Any], llm_client: Any) -> list[dict[str, Any]]:
    """Main entry: dual-channel extraction with merge."""
    print_section("Dual-Channel Form Extraction")

    # Channel A: Rule-based (always run)
    rule_fields = extract_fields_rule_based(page)

    # Channel B: AI analysis
    ai_result = extract_fields_ai(page, profile, llm_client)

    if "error" in ai_result:
        print(f"AI extraction failed: {ai_result['error']}, using rule-based results only")
        for f in rule_fields:
            f["source"] = "rule"
        return rule_fields

    # Merge
    merged = merge_extraction_results(rule_fields, ai_result)
    return merged


def _extract_form_html(page: Page) -> str:
    """Extract form HTML from page, including iframe content."""
    htmls = []
    
    # Extract from main frame
    main_html = _extract_form_html_from_frame(page)
    if main_html:
        htmls.append(f"<!-- MAIN FRAME -->\n{main_html}")
    
    # Extract from all frames
    try:
        frames = page.frames
        for i, frame in enumerate(frames):
            if frame == page.main_frame:
                continue  # Skip main frame, already processed
            try:
                frame_html = _extract_form_html_from_frame(frame)
                if frame_html:
                    frame_name = frame.name or f"frame_{i}"
                    frame_url = frame.url
                    htmls.append(f"<!-- FRAME: {frame_name} ({frame_url}) -->\n{frame_html}")
            except Exception as e:
                print(f"Warning: Failed to extract from frame {i}: {e}")
    except Exception as e:
        print(f"Warning: Failed to enumerate frames: {e}")
    
    return "\n\n".join(htmls) if htmls else ""


def _extract_form_html_from_frame(page_or_frame) -> str:
    """Extract form HTML from a specific frame."""
    script = '''
    () => {
        const formSelectors = [
            'form', '[class*="form"]', '[class*="Form"]',
            '[id*="form"]', '[id*="Form"]',
            '.ant-form', '.el-form', '.arco-form', '[role="form"]',
            'main', '.main', '.content', '.page-content',
            '[class*="page"]', '[class*="container"]',
        ];

        let bestElement = null;
        let maxInputCount = 0;

        for (const selector of formSelectors) {
            try {
                const elements = document.querySelectorAll(selector);
                for (const el of elements) {
                    const inputCount = el.querySelectorAll(
                        'input, textarea, select, [role="textbox"], [role="combobox"], [contenteditable="true"]'
                    ).length;
                    if (inputCount > maxInputCount) {
                        maxInputCount = inputCount;
                        bestElement = el;
                    }
                }
            } catch (e) {}
        }

        if (!bestElement || maxInputCount < 3) {
            bestElement = document.body;
        }

        return bestElement ? bestElement.outerHTML : document.body.outerHTML;
    }
    '''
    
    try:
        return page_or_frame.evaluate(script)
    except Exception as e:
        print(f"Warning: Form HTML extraction failed: {e}")
        return ""


def _clean_html(html: str) -> str:
    import re
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'\sstyle="[^"]*"', '', html)
    html = re.sub(r'\s(on[a-z]*="[^"]*")', '', html)
    html = re.sub(r'\n\s*\n', '\n', html)
    html = re.sub(r'\s{2,}', ' ', html)
    if len(html) > 30000:
        html = html[:30000] + "... [HTML truncated for AI analysis]"
    return html.strip()


def _build_ai_extraction_prompt(html: str, profile: dict[str, Any]) -> str:
    profile_json = json.dumps(profile, ensure_ascii=False, indent=2)
    if len(profile_json) > 6000:
        profile_json = profile_json[:6000] + "... [profile truncated]"

    return f"""你是一个专业的表单自动填充专家。请分析以下HTML表单结构，识别所有需要填写的字段，并基于用户档案数据生成精确的填写计划。

## HTML表单结构

```html
{html}
```

## 用户档案数据

```json
{profile_json}
```

## 分析任务

请仔细分析HTML结构，找出所有可填写的表单字段，并为每个字段生成填写计划。

### 要求

1. **全面识别字段** - 识别所有input、textarea、select等表单元素，包括文件上传、日期选择、下拉框、radio、checkbox等，不要遗漏任何字段
2. **智能匹配数据** - 将表单字段与用户档案数据进行语义匹配，理解字段的上下文含义
3. **生成精确选择器** - 为每个字段生成可靠的CSS选择器和XPath，优先使用id、name等稳定属性
4. **正确分类处理** - 敏感字段（身份证、政治面貌等）标记为manual；文件上传字段特殊处理
5. **指定填写策略** - 每个字段标注fill_strategy: text/select/radio_click/checkbox_click/datepicker/upload/cascader/contenteditable

### 输出格式

```json
{{
  "analysis_summary": {{
    "total_fields": 0,
    "fillable_fields": 0,
    "form_type": "表单类型描述"
  }},
  "fields": [
    {{
      "field_id": "唯一标识",
      "field_name": "字段名称/用途",
      "field_type": "input类型",
      "selector": "CSS选择器",
      "xpath": "XPath选择器",
      "required": true,
      "fill_strategy": "text|select|radio_click|checkbox_click|datepicker|upload|cascader|contenteditable",
      "matched_data": {{
        "value": "要填入的值",
        "source": "数据来源路径",
        "confidence": 0.95,
        "reason": "匹配理由"
      }},
      "fill_action": "auto_fill|manual|skip",
      "options": [],
      "notes": ""
    }}
  ],
  "unmatchable_fields": []
}}
```

### 重要提示

- 对于下拉菜单(select/combobox)，在options中列出所有选项
- 对于radio组，在options中列出所有选项的text和value
- 对于checkbox，标注哪些选项应该被选中
- 对于日期字段，标注fill_strategy为datepicker
- 对于省市区级联选择，标注fill_strategy为cascader
- 敏感字段（身份证号、政治面貌等）标记fill_action为manual
- 文件上传字段标注fill_strategy为upload

请开始分析。"""
