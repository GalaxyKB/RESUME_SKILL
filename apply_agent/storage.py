from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

from .config import DATA_DIR, OUTPUTS_DIR, RECORDS_DIR


APPLICATION_FIELDS = [
    "date",
    "company",
    "position",
    "url",
    "status",
    "match_score",
    "notes",
    "fill_plan_path",
    "jd_analysis_path",
]


def _as_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)


def load_yaml(path: str | Path) -> Any:
    file_path = _as_path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    return content if content is not None else {}


def save_json(path: str | Path, data: Any) -> None:
    file_path = _as_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def load_text(path: str | Path) -> str:
    file_path = _as_path(path)
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def ensure_dirs() -> None:
    required_dirs = [
        DATA_DIR,
        OUTPUTS_DIR,
        OUTPUTS_DIR / "jd_analysis",
        OUTPUTS_DIR / "tailored_texts",
        OUTPUTS_DIR / "fill_plans",
        OUTPUTS_DIR / "screenshots",
        OUTPUTS_DIR / "logs",
        OUTPUTS_DIR / "logs" / "json_parse_errors",
        RECORDS_DIR,
    ]
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)


def append_application_record(record: dict[str, Any]) -> Path:
    ensure_dirs()
    csv_path = RECORDS_DIR / "applications.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=APPLICATION_FIELDS)
        if not file_exists:
            writer.writeheader()
        row = {field: record.get(field, "") for field in APPLICATION_FIELDS}
        writer.writerow(row)
    return csv_path
