from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .config import RECORDS_DIR
from .storage import ensure_dirs


FIELDS = [
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


def init_records() -> Path:
    ensure_dirs()
    csv_path = RECORDS_DIR / "applications.csv"
    if not csv_path.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
    return csv_path


def append_application(record: dict[str, Any]) -> Path:
    csv_path = init_records()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writerow({field: record.get(field, "") for field in FIELDS})
    return csv_path
