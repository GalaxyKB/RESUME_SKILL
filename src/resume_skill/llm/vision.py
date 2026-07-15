from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

from ..config import AppConfig, CONFIG
from .ark_provider import ArkChatVisionProvider, ArkResponsesProvider


class VisionWorkflowAdapter:
    """Adapter exposing workflow-specific vision methods over generic LLM providers."""

    def __init__(self, provider: ArkResponsesProvider | ArkChatVisionProvider):
        self.provider = provider

    def verify(self, screenshot: Any, snapshot: Any, prompt: str) -> str:
        image_bytes = self._extract_image_bytes(screenshot)
        prompt = self._compact_prompt(prompt, snapshot)
        if image_bytes and hasattr(self.provider, "call_vision_text"):
            errors = []
            for max_width, quality, max_height in ((960, 78, 2600), (720, 74, 2200), (520, 70, 1800)):
                compressed = self._compress_image(image_bytes, max_width=max_width, quality=quality, max_height=max_height)
                try:
                    return self._normalize_verify_json(self.provider.call_vision_text(prompt, compressed, mime_type="image/jpeg"))
                except Exception as exc:
                    errors.append(f"{max_width}px/q{quality}: {exc}")

            text_result = self._verify_from_text(prompt, snapshot)
            try:
                data = json.loads(text_result)
                data["summary"] = (data.get("summary", "") + " | image attempts failed: " + " ; ".join(errors[-2:]))[:1000]
                return json.dumps(data, ensure_ascii=False)
            except Exception:
                return text_result

        return self._verify_from_text(prompt, snapshot)

    def _verify_from_text(self, prompt: str, snapshot: Any) -> str:
        snapshot_text = self._stringify(snapshot)[:5000]
        text_prompt = f"""{prompt}

No usable screenshot bytes were available. Verify from the accessibility snapshot and recent state instead.

Snapshot:
{snapshot_text}

Return only JSON matching the requested schema."""
        try:
            return self._normalize_verify_json(self.provider.call_text("", text_prompt))
        except Exception as exc:
            return json.dumps({
                "action_success": False,
                "page_success": False,
                "summary": f"vision text fallback failed: {exc}",
                "issues": [],
                "next_actions": [],
                "manual_required": False,
            }, ensure_ascii=False)

    def get_recovery_actions(self, snapshot: Any, errors: list[str], prompt: str) -> str:
        text_prompt = f"""{prompt}

Snapshot:
{self._stringify(snapshot)}

Errors:
{json.dumps(errors, ensure_ascii=False)}

Return only a JSON array."""
        return self.provider.call_text("", text_prompt)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.provider, name)

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, str):
            return value[:12000]
        try:
            return json.dumps(value, ensure_ascii=False)[:12000]
        except Exception:
            return str(value)[:12000]

    def _extract_image_bytes(self, screenshot: Any) -> bytes | None:
        if not screenshot:
            return None
        if isinstance(screenshot, bytes):
            return screenshot
        if isinstance(screenshot, str):
            return self._decode_image_string(screenshot)
        if isinstance(screenshot, dict):
            for key in ("data", "screenshot", "image", "base64"):
                data = screenshot.get(key)
                decoded = self._extract_image_bytes(data)
                if decoded:
                    return decoded
            content = screenshot.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        for key in ("data", "text"):
                            decoded = self._extract_image_bytes(item.get(key))
                            if decoded:
                                return decoded
        return None

    @staticmethod
    def _decode_image_string(value: str) -> bytes | None:
        text = value.strip()
        if not text:
            return None
        if text.startswith("data:image") and "," in text:
            text = text.split(",", 1)[1]
        try:
            return base64.b64decode(text, validate=True)
        except Exception:
            return None

    @staticmethod
    def _compress_image(image_bytes: bytes, max_width: int = 1280, quality: int = 82, max_height: int = 3600) -> bytes:
        try:
            from PIL import Image

            with Image.open(io.BytesIO(image_bytes)) as img:
                img = img.convert("RGB")
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    img = img.resize((max_width, max(1, int(img.height * ratio))))
                if img.height > max_height:
                    ratio = max_height / float(img.height)
                    img = img.resize((max(1, int(img.width * ratio)), max_height))
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=quality, optimize=True)
                return out.getvalue()
        except Exception:
            return image_bytes

    @staticmethod
    def _compact_prompt(prompt: str, snapshot: Any) -> str:
        snapshot_text = VisionWorkflowAdapter._stringify(snapshot)[:4000]
        return f"""{prompt[:4000]}

Accessibility snapshot excerpt:
{snapshot_text}

Return strict JSON only."""

    @staticmethod
    def _normalize_verify_json(text: str) -> str:
        try:
            data = json.loads(text)
        except Exception:
            import re

            match = re.search(r"\{.*\}", str(text), re.S)
            data = json.loads(match.group(0)) if match else {"summary": str(text)[:500]}
        return json.dumps({
            "action_success": bool(data.get("action_success", data.get("ok", False))),
            "page_success": bool(data.get("page_success", data.get("ok", False))),
            "summary": str(data.get("summary", ""))[:1000],
            "issues": data.get("issues", []) if isinstance(data.get("issues", []), list) else [],
            "next_actions": data.get("next_actions", []) if isinstance(data.get("next_actions", []), list) else [],
            "manual_required": bool(data.get("manual_required", False)),
        }, ensure_ascii=False)


def create_vision_client(config: AppConfig | None = None, outputs_dir: Path | None = None) -> ArkResponsesProvider | ArkChatVisionProvider | None:
    cfg = config or CONFIG
    if not cfg.vision.enabled:
        return None
    provider = cfg.vision.provider.lower()
    if provider not in {"ark", "ark_responses", "ark_chat", "doubao", "volcengine"}:
        raise RuntimeError(f"Unsupported vision provider: {cfg.vision.provider}")
    if not cfg.vision.api_key:
        raise RuntimeError("Vision API key not configured. Set VISION_API_KEY or ARK_API_KEY in .env.")

    log_dir = outputs_dir or cfg.outputs_dir / "logs"
    provider_cls = ArkChatVisionProvider if provider == "ark_chat" else ArkResponsesProvider
    return provider_cls(
        api_key=cfg.vision.api_key,
        base_url=cfg.vision.base_url,
        model=cfg.vision.model,
        log_path=log_dir / "vision_calls.jsonl",
        parse_error_dir=log_dir / "json_parse_errors",
    )


def check_vision_health(config: AppConfig | None = None) -> dict[str, Any]:
    cfg = config or CONFIG
    provider = create_vision_client(cfg)
    if not provider:
        return {"ok": False, "error": "vision disabled", "provider": cfg.vision.provider, "model": cfg.vision.model}
    prompt = '请观察图片并只返回JSON：{"ok":true,"summary":"一句话描述","saw_image":true}'
    try:
        if hasattr(provider, "call_vision_text"):
            text = provider.call_vision_text(prompt, _health_check_image())
        else:
            text = provider.call_text("", "视觉健康检查：请返回JSON：{\"ok\":true,\"summary\":\"text-only fallback\",\"saw_image\":false}")
        normalized = VisionWorkflowAdapter._normalize_verify_json(text)
        data = json.loads(normalized)
        data.update({"provider": cfg.vision.provider, "model": cfg.vision.model})
        data["ok"] = bool(data.get("action_success") or data.get("page_success") or data.get("summary"))
        return data
    except Exception as exc:
        return {"ok": False, "error": str(exc), "provider": cfg.vision.provider, "model": cfg.vision.model}


def _health_check_image() -> bytes:
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (320, 160), "white")
        draw = ImageDraw.Draw(img)
        draw.rectangle((20, 20, 300, 140), outline="black", width=2)
        draw.text((40, 65), "VISION HEALTH", fill="black")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=80)
        return out.getvalue()
    except Exception:
        return base64.b64decode(
            "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/ASP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/ASP/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
        )
