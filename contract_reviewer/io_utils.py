"""Run identity, safe filenames, and per-run JSON artifact persistence."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contract_reviewer.config import PROJECT_ROOT

RUNS_DIR = PROJECT_ROOT / ".runs"
REVIEWS_DIR = PROJECT_ROOT / "Reviews"
REPORTS_DIR = PROJECT_ROOT / "Reports"
SUMMARY_DIR = PROJECT_ROOT / "Summary"

_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def new_run_id() -> str:
    return f"{utc_timestamp()}-{uuid.uuid4().hex[:8]}"


def safe_filename_stem(name: str) -> str:
    stem = Path(name).stem
    safe = _UNSAFE_CHARS_RE.sub("-", stem).strip("-")
    return safe or "contract"


def _default_output_path(
    directory: Path, extension: str, source_filename: str, run_id: str
) -> Path:
    safe_name = safe_filename_stem(source_filename)
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / f"{safe_name}-{run_id}.{extension}"
    suffix = 1
    while candidate.exists():
        candidate = directory / f"{safe_name}-{run_id}-{suffix}.{extension}"
        suffix += 1
    return candidate


def default_report_path(source_filename: str, run_id: str) -> Path:
    return _default_output_path(REVIEWS_DIR, "md", source_filename, run_id)


def default_pdf_path(source_filename: str, run_id: str) -> Path:
    return _default_output_path(REPORTS_DIR, "pdf", source_filename, run_id)


def default_summary_path(source_filename: str, run_id: str) -> Path:
    return _default_output_path(SUMMARY_DIR, "docx", source_filename, run_id)


def run_artifact_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_artifact(run_id: str, name: str, data) -> None:
    path = run_artifact_dir(run_id) / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
