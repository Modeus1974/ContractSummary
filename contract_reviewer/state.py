"""LangGraph state: a flat, JSON-serializable TypedDict shared across all nodes.

`model_assignments` and `errors` use an additive reducer because the verify and
factual_check nodes run as parallel branches in the same superstep and each may need
to append to them; every other field has exactly one writer per superstep.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ReviewState(TypedDict, total=False):
    # Run identity / source
    run_id: str
    started_at_utc: str
    source_pdf_path: str
    source_sha256: str
    source_filename_safe: str
    client_role: str | None
    client_perspective: str | None
    research_date: str
    max_cycles: int
    output_path_override: str | None

    # Stage 1 — intake and classification
    extraction: dict  # {text, pages: [{page_no, text}], warnings, scanned_pages, ok}
    extraction_ok: bool
    skill_content_hashes: dict  # path -> sha256
    classification_attempt: int
    routing_record: dict
    routing_needs_reviewer_resolution: bool
    selected_skill_texts: dict  # path -> full verbatim markdown

    # Stage 2 / correction cycles
    correction_cycle: int
    draft_findings: list  # Finding.model_dump()[]
    authority_ledger: list  # Authority.model_dump()[]
    documents_and_issue_areas_considered: list
    areas_with_no_material_finding: list
    revision_brief: dict | None

    # Stage 3 — verification and factual checking
    verification_records: list
    factual_check_notes: list
    verifier_newly_identified_findings: (
        list  # not auto-approved; reconcile routes back to review
    )
    verifier_unsupported_assertions: list

    # Stage 4 — reconcile / release gate
    defects_pending: bool
    correction_log: list
    unresolved_material_disagreement: bool
    report_status: str  # Completed | Provisional | Incomplete
    commercial_recommendation: str
    unverified_concerns: list

    # Cross-cutting
    model_assignments: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]
    incomplete_reason: str | None

    # Stage 5 — report
    final_markdown: str
    report_context: (
        dict  # kwargs used to render the Markdown/PDF templates, shared by both
    )
    output_path: str
    pdf_output_path: str | None
