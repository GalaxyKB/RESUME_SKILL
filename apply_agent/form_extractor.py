from __future__ import annotations

from typing import Any

from playwright.sync_api import Page


def extract_form_fields(page: Page) -> list[dict[str, Any]]:
    script = r'''
    () => {
      const escapeCss = (value) => {
        if (window.CSS && CSS.escape) {
          return CSS.escape(value);
        }
        return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
      };

      const isVisible = (el) => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style && style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
      };

      const getLabelText = (el) => {
        const id = el.getAttribute('id');
        if (id) {
          const label = document.querySelector(`label[for="${escapeCss(id)}"]`);
          if (label) {
            return label.innerText || label.textContent || '';
          }
        }
        
        const closestLabel = el.closest('label');
        if (closestLabel) {
          return closestLabel.innerText || closestLabel.textContent || '';
        }
        
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) {
          return ariaLabel;
        }
        
        const immediateParent = el.parentElement;
        if (immediateParent && immediateParent.children.length < 5) {
          let parentText = '';
          for (const child of immediateParent.children) {
            if (child === el) continue;
            const text = (child.textContent || '').trim();
            if (text && text.length < 60) {
              parentText = text;
              break;
            }
          }
          if (parentText) return parentText;
        }
        
        if (immediateParent) {
          let textContent = '';
          for (const node of immediateParent.childNodes) {
            if (node.nodeType === 3) {
              const text = node.textContent.trim();
              if (text && text.length < 60) {
                textContent = text;
                break;
              }
            }
          }
          if (textContent) return textContent;
        }
        
        return '';
      };

      const toXPath = (el) => {
        if (!el || el.nodeType !== 1) {
          return '';
        }
        if (el.id) {
          return `//*[@id="${String(el.id).replace(/"/g, '\\"')}"]`;
        }
        const parts = [];
        let current = el;
        while (current && current.nodeType === 1) {
          let index = 1;
          let sibling = current.previousElementSibling;
          while (sibling) {
            if (sibling.tagName === current.tagName) {
              index += 1;
            }
            sibling = sibling.previousElementSibling;
          }
          parts.unshift(`${current.tagName.toLowerCase()}[${index}]`);
          current = current.parentElement;
        }
        return '/' + parts.join('/');
      };

      const makeSelector = (el) => {
        const tag = el.tagName.toLowerCase();
        const id = el.getAttribute('id');
        if (id) {
          return `#${escapeCss(id)}`;
        }
        const name = el.getAttribute('name');
        if (name) {
          return `${tag}[name="${String(name).replace(/"/g, '\\"')}"]`;
        }
        const aria = el.getAttribute('aria-label');
        if (aria) {
          return `${tag}[aria-label="${String(aria).replace(/"/g, '\\"')}"]`;
        }
        const type = el.getAttribute('type');
        if (type) {
          const scope = el.parentElement || document.body;
          const same = Array.from(scope.querySelectorAll(tag));
          const index = same.indexOf(el) + 1;
          return `${tag}:nth-of-type(${index})`;
        }
        const scope = el.parentElement || document.body;
        const same = Array.from(scope.querySelectorAll(tag));
        const index = same.indexOf(el) + 1;
        return `${tag}:nth-of-type(${index})`;
      };

      const elements = Array.from(
        document.querySelectorAll(
          'input, textarea, select, [role="textbox"], [role="combobox"], [contenteditable="true"], button, [role="button"]'
        )
      );
      const result = [];
      let counter = 1;

      for (const el of elements) {
        const tag = el.tagName.toLowerCase();
        const role = (el.getAttribute('role') || '').toLowerCase();
        const type = (el.getAttribute('type') || '').toLowerCase();
        const disabled = el.disabled || el.getAttribute('disabled') !== null;
        const hidden = type === 'hidden' || type === 'submit' || type === 'button' || type === 'reset';
        const isContentEditable = (el.getAttribute('contenteditable') || '').toLowerCase() === 'true';
        const isButtonLike = tag === 'button' || role === 'button';
        const isTextboxLike = tag === 'input' || tag === 'textarea' || role === 'textbox' || isContentEditable;
        const isSelectLike = tag === 'select' || role === 'combobox';

        if (disabled || (hidden && !isButtonLike)) {
          continue;
        }
        if (!isVisible(el) && tag !== 'input' && type !== 'file' && !isTextboxLike && !isSelectLike && !isButtonLike) {
          continue;
        }

        const label = getLabelText(el).replace(/\s+/g, ' ').trim();
        const placeholder = (el.getAttribute('placeholder') || '').trim();
        const name = (el.getAttribute('name') || '').trim();
        const id = (el.getAttribute('id') || '').trim();
        const ariaLabel = (el.getAttribute('aria-label') || '').trim();
        
        let nearby = '';
        const parent = el.parentElement;
        if (parent) {
          const siblings = [];
          for (const child of parent.children) {
            if (child === el) continue;
            const text = (child.textContent || '').trim();
            if (text && text.length < 100) {
              siblings.push(text);
            }
          }
          nearby = siblings.slice(0, 3).join(' ').slice(0, 150);
        }
        
        const options = [];
        if (tag === 'select') {
          for (const option of Array.from(el.options || [])) {
            options.push({ text: (option.textContent || '').trim(), value: option.value, selected: option.selected });
          }
        }

        const hasUsefulHint = Boolean(label || placeholder || name || id || ariaLabel || nearby);
        if (!hasUsefulHint) {
          continue;
        }

        const plainHints = [placeholder, name, id, ariaLabel].filter(Boolean).join(' ');
        const looksLikeContainerNoise =
          !plainHints &&
          ((label && label.length > 100) || (nearby && nearby.length > 140));
        if (looksLikeContainerNoise) {
          continue;
        }

        if (tag === 'textarea' && !plainHints && !placeholder) {
          continue;
        }

        if ((tag === 'textarea' || isContentEditable) && !plainHints && label && label.length > 80) {
          continue;
        }

        if (isButtonLike) {
          const buttonText = `${label} ${nearby}`.toLowerCase();
          const uploadLike = /上传|upload|附件|简历|resume|cv/.test(buttonText);
          if (!uploadLike) {
            continue;
          }
        }

        result.push({
          field_id: `field_${String(counter).padStart(3, '0')}`,
          selector: makeSelector(el),
          xpath: toXPath(el),
          tag,
          type,
          role,
          is_textbox_like: isTextboxLike,
          is_select_like: isSelectLike,
          is_button_like: isButtonLike,
          label,
          placeholder,
          name,
          id,
          aria_label: ariaLabel,
          nearby_text: nearby.slice(0, 200),
          options,
        });
        counter += 1;
      }

      return result;
    }
    '''

    aggregated: list[dict[str, Any]] = []
    dedupe: set[tuple[str, str]] = set()
    counter = 1
    for frame in page.frames:
        try:
            items = frame.evaluate(script)
        except Exception:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item = dict(item)
            selector = str(item.get("selector", ""))
            xpath = str(item.get("xpath", ""))
            signature = (selector, xpath)
            if signature in dedupe:
              continue
            dedupe.add(signature)
            item["field_id"] = f"field_{str(counter).zfill(3)}"
            item["frame_url"] = frame.url
            aggregated.append(item)
            counter += 1
    return aggregated
