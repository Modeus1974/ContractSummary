"""Stage 2: the Flagship-reasoning legal reviewer. Produces/revises findings and the
authority ledger, using bound web search to find and confirm primary Singapore legal
sources rather than inventing citations."""

from __future__ import annotations

from langchain_tavily import TavilySearch

from contract_reviewer import models, prompts
from contract_reviewer.logging_setup import log_model_assignment, log_stage
from contract_reviewer.runtime import get_tiers
from contract_reviewer.schemas import ReviewDraft
from contract_reviewer.state import ReviewState


def review_node(state: ReviewState) -> dict:
    cycle = state.get("correction_cycle", 0)
    log_stage("review", f"cycle={cycle}")
    tier = get_tiers()["flagship"]

    messages = prompts.build_review_messages(
        contract_text=state["extraction"]["text"],
        routing_record=state["routing_record"],
        selected_skill_texts=state["selected_skill_texts"],
        revision_brief=state.get("revision_brief"),
        prior_findings=state.get("draft_findings"),
        prior_authorities=state.get("authority_ledger"),
    )
    draft, assignment = models.invoke_structured(
        tier,
        "legal_reviewer",
        messages,
        ReviewDraft,
        tools=[TavilySearch(max_results=5)],
    )
    log_model_assignment(assignment)

    return {
        "draft_findings": [f.model_dump() for f in draft.findings],
        "authority_ledger": [a.model_dump() for a in draft.authorities],
        "documents_and_issue_areas_considered": draft.documents_and_issue_areas_considered,
        "areas_with_no_material_finding": draft.areas_with_no_material_finding,
        "model_assignments": [assignment.model_dump()],
    }
