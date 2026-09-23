"""Console logging: one line per stage transition, plus real model assignments used."""

from __future__ import annotations

import logging

from contract_reviewer.schemas import ModelAssignment

logger = logging.getLogger("contract_reviewer")


def configure_logging(verbose: bool) -> None:
    """Only our own logger gets verbose; third-party libraries (httpx, anthropic's SDK,
    etc.) stay at WARNING so `-v` doesn't dump raw HTTP traffic and tool schemas."""
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


def log_stage(stage: str, detail: str = "") -> None:
    logger.info(f"[stage] {stage}{': ' + detail if detail else ''}")


def log_model_assignment(assignment: ModelAssignment) -> None:
    logger.info(
        f"[model] role={assignment.role} tier={assignment.tier} "
        f"provider={assignment.provider} model={assignment.model} "
        f"effort={assignment.effort_actual}"
    )


def log_warning(message: str) -> None:
    logger.warning(f"[warn] {message}")
