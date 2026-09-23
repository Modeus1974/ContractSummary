"""The contract-summary pipeline: extract -> summarise -> fidelity-check -> return.

Deliberately a plain linear function, not a LangGraph graph -- see summary.md: this task
has no branching and no correction loop to bound/checkpoint, unlike the risk-review workflow.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from contract_reviewer import document_extract, models, pdf_extract, prompts
from contract_reviewer.config import TierConfig
from contract_reviewer.schemas import ContractSummary

_NOT_STATED = ("not stated", "not specified", "none", "n/a")
_MONEY_RE = re.compile(r"S?\$\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?")
_DATE_RE = re.compile(
    r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(r"\d+\s*(?:day|days|week|weeks|month|months|year|years)", re.IGNORECASE)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _fidelity_issues(contract_text: str, summary: ContractSummary) -> list[str]:
    """Reuses the substring-check idea from nodes/factual_check.py, but checks the concrete
    figures/dates *within* each field rather than the whole field verbatim -- the model
    legitimately writes these as short sentences with clause context, not bare values, so a
    whole-string check would flag every correct answer as a false positive. Whitespace is
    normalized on both sides since PDF extraction can insert a line break mid-phrase (e.g.
    "the 1st\nof each month") that a naive substring check would otherwise misreport as a
    fabricated fact rather than a line-wrap artifact."""
    issues: list[str] = []
    normalized_source = _normalize_whitespace(contract_text)

    def check(value: str | None) -> None:
        value = (value or "").strip()
        if not value or value.lower() in _NOT_STATED:
            return
        tokens = _MONEY_RE.findall(value) + _DATE_RE.findall(value) + _DURATION_RE.findall(value)
        if not tokens:
            tokens = [value]  # no extractable figure/date -- fall back to the whole value
        for token in tokens:
            if _normalize_whitespace(token) not in normalized_source:
                issues.append(
                    f"'{token}' (from '{value}') could not be matched verbatim in the source "
                    "text -- verify against the original."
                )

    check(summary.key_monetary_value)
    check(summary.effective_date)
    check(summary.term_duration)
    for key_date in summary.key_dates:
        check(key_date.date)
    return issues


def run_summary(
    source_path: str,
    tier: TierConfig,
    client_role: str | None = None,
    on_stage: Callable[[str], None] | None = None,
) -> dict:
    """Returns {ok, source_sha256, extraction_warnings, summary, fidelity_issues,
    model_assignment, incomplete_reason}. Never raises on a bad source file.

    `on_stage`, if given, is called with "extracting" then "summarizing" at the two points
    a caller (e.g. the Django web task) might want to report progress -- purely a reporting
    hook, no branching depends on it, so the CLI can ignore it entirely."""
    path = Path(source_path)
    if not path.is_file():
        return {"ok": False, "incomplete_reason": f"Source file not found: {path}"}

    if on_stage:
        on_stage("extracting")
    source_sha256 = pdf_extract.sha256_file(path)
    extraction = document_extract.extract_document(path)
    if not extraction["ok"]:
        return {
            "ok": False,
            "source_sha256": source_sha256,
            "extraction_warnings": extraction["warnings"],
            "incomplete_reason": "Document could not be read or contains no extractable text: "
            + "; ".join(extraction["warnings"]),
        }

    if on_stage:
        on_stage("summarizing")
    messages = prompts.build_summary_messages(contract_text=extraction["text"], client_role=client_role)
    summary, assignment = models.invoke_structured(tier, "summarizer", messages, ContractSummary)

    return {
        "ok": True,
        "source_sha256": source_sha256,
        "extraction_warnings": extraction["warnings"],
        "summary": summary,
        "fidelity_issues": _fidelity_issues(extraction["text"], summary),
        "model_assignment": assignment,
    }
