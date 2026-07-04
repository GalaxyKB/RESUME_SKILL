from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console


console = Console()


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_filename(text: str) -> str:
    cleaned = re.sub(r'[<>:\"/\\|?*\x00-\x1f]', "_", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned[:120] or "file"


def print_section(title: str) -> None:
    console.rule(f"[bold cyan]{title}[/bold cyan]")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clip_text(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[:length]


def safe_path_text(path: str | Path) -> str:
    return str(path)


def to_plain_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(to_plain_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {to_plain_text(val)}" for key, val in value.items())
    return str(value)
