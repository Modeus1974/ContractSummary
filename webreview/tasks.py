"""Background task: runs the contract_reviewer summariser for one Summary and persists
progress/results as it goes. Enqueued via django-q2's async_task() from views.py.

The risk-review pipeline (LangGraph-based, Review/Finding/Authority/VerificationRecord/
RunEvent models) has been removed from this web app -- see CLAUDE.md's "web app is now
summary-only" note. The CLI (review.py) and contract_reviewer/graph.py are unaffected;
this file only ever drove the web app's own task queue.
"""
from __future__ import annotations

import logging

from django.core.files.base import ContentFile
from django.utils import timezone as django_timezone

from contract_reviewer import config as cr_config
from contract_reviewer import summary_pdf_report
from contract_reviewer.summarize import run_summary
from webreview.models import Summary

logger = logging.getLogger("webreview")

_SUMMARY_STAGE_LABELS = {"extracting": "Reading document", "summarizing": "Summarising"}
_SUMMARY_STAGE_PROGRESS = {"extracting": 20, "summarizing": 60}


def run_summary_task(summary_id: int) -> None:
    """Background task for the Contract Summary feature (Specifications.md §12). No
    LangGraph here -- summarize.run_summary() is a single linear call, not a graph, so
    progress is just the two on_stage() hooks it calls, not a stream() loop."""
    summary_run = Summary.objects.select_related("document", "contract").get(id=summary_id)
    logger.info("Summary %s: task starting (document=%s)", summary_id, summary_run.document.original_filename)
    summary_run.execution_status = Summary.RUNNING
    summary_run.started_at = django_timezone.now()
    summary_run.save(update_fields=["execution_status", "started_at", "updated_at"])

    try:
        _execute_summary(summary_run)
    except Exception as exc:  # bug in this glue code / infra failure, not a caught extraction error
        logger.exception("Summary %s: task failed", summary_id)
        summary_run.execution_status = Summary.FAILED
        summary_run.incomplete_reason = f"Task failed: {exc}"
        summary_run.completed_at = django_timezone.now()
        summary_run.save(update_fields=["execution_status", "incomplete_reason", "completed_at", "updated_at"])


def _execute_summary(summary_run: Summary) -> None:
    cr_config.load_env()
    tier = cr_config.load_tier_config()["balanced"]

    def on_stage(stage: str) -> None:
        logger.info("Summary %s: stage=%s", summary_run.id, stage)
        summary_run.current_stage_label = _SUMMARY_STAGE_LABELS.get(stage, stage)
        summary_run.progress_percent = _SUMMARY_STAGE_PROGRESS.get(stage, summary_run.progress_percent)
        summary_run.save(update_fields=["current_stage_label", "progress_percent", "updated_at"])

    result = run_summary(
        summary_run.document.file.path,
        tier,
        client_role=summary_run.contract.client_role or None,
        on_stage=on_stage,
    )

    if not result["ok"]:
        logger.warning("Summary %s: extraction not ok -- %s", summary_run.id, result["incomplete_reason"])
        summary_run.execution_status = Summary.SUCCEEDED  # the task itself completed even though extraction failed
        summary_run.incomplete_reason = result["incomplete_reason"]
        summary_run.progress_percent = 100
        summary_run.completed_at = django_timezone.now()
        summary_run.save()
        return

    context = {
        "source_filename": summary_run.document.original_filename,
        "source_sha256": result["source_sha256"],
        "client_role": summary_run.contract.client_role or None,
        "generated_at": django_timezone.now().strftime("%Y-%m-%d %H:%M UTC"),
        "fidelity_issues": result["fidelity_issues"],
    }
    summary_run.summary_context = {**context, "summary": result["summary"].model_dump()}
    summary_run.fidelity_issues = result["fidelity_issues"]
    summary_run.execution_status = Summary.SUCCEEDED
    summary_run.progress_percent = 100
    summary_run.completed_at = django_timezone.now()
    summary_run.save()
    logger.info("Summary %s: succeeded", summary_run.id)

    try:
        pdf_bytes = summary_pdf_report.render_pdf(result["summary"], context)
        summary_run.summary_pdf.save(f"{summary_run.run_id}.pdf", ContentFile(pdf_bytes), save=True)
    except Exception as exc:
        # Same non-fatal handling as the review's PDF rendering: the summary itself is
        # still a success, the PDF just isn't available for download.
        logger.exception("Summary %s: PDF rendering failed", summary_run.id)
        summary_run.incomplete_reason = (summary_run.incomplete_reason + f" PDF rendering failed: {exc}").strip()
        summary_run.save(update_fields=["incomplete_reason"])
