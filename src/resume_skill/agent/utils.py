from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console

from ..config import CONFIG


console = Console()


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_filename(text: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
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


def to_plain_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(to_plain_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {to_plain_text(val)}" for key, val in value.items())
    return str(value)


def ensure_dirs() -> None:
    dirs = [
        CONFIG.outputs_dir,
        CONFIG.outputs_dir / "jd_analysis",
        CONFIG.outputs_dir / "tailored_texts",
        CONFIG.outputs_dir / "fill_plans",
        CONFIG.outputs_dir / "screenshots",
        CONFIG.outputs_dir / "logs",
        CONFIG.outputs_dir / "logs" / "json_parse_errors",
        CONFIG.records_dir,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def load_yaml(path: str | Path) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as f:
        content = yaml.safe_load(f)
    return content if content is not None else {}


def save_json(path: str | Path, data: Any) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_text(path: str | Path) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


APPLICATION_FIELDS = [
    "date", "company", "position", "url", "status",
    "match_score", "notes", "fill_plan_path", "jd_analysis_path",
]


def init_records() -> Path:
    ensure_dirs()
    csv_path = CONFIG.records_dir / "applications.csv"
    if not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=APPLICATION_FIELDS)
            writer.writeheader()
    return csv_path


def append_application(record: dict[str, Any]) -> Path:
    csv_path = init_records()
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=APPLICATION_FIELDS)
        writer.writerow({field: record.get(field, "") for field in APPLICATION_FIELDS})
    return csv_path


def find_resume_pdf() -> str:
    search_dirs = [
        CONFIG.personal_info_dir / "formal_resume",
        CONFIG.project_root / "data",
        CONFIG.project_root,
    ]
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        pdf_files = sorted(search_dir.glob("*.pdf"))
        if pdf_files:
            chinese_pdfs = [p for p in pdf_files if any(ord(c) > 0x4E00 for c in p.stem)]
            selected = max(chinese_pdfs, key=lambda p: len(p.stem)) if chinese_pdfs else pdf_files[0]
            print(f"Found resume: {selected.name}")
            return str(selected)

    default_path = CONFIG.personal_info_dir / "formal_resume" / "resume.pdf"
    print(f"Warning: No resume PDF found. Expected in: {CONFIG.personal_info_dir / 'formal_resume'}/")
    return str(default_path)
