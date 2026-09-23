"""Stage 3a: the independent verifier. A genuinely separate agent from the reviewer --
its own fresh message list and its own model client instance, built only from the
reviewer's final findings/ledger, never the reviewer's reasoning transcript."""

from __future__ import annotations

from langchain_tavily import TavilySearch

from contract_reviewer import models, prompts
from contract_reviewer.logging_setup import log_model_assignment, log_stage
from contract_reviewer.runtime import get_tiers
from contract_reviewer.schemas import VerificationDraft
from contract_reviewer.state import ReviewState


def verify_node(state: ReviewState) -> dict:
    log_stage("verify", f"cycle={state.get('correction_cycle', 0)}")
    tier = get_tiers()["flagship"]

    messages = prompts.build_verify_messages(
        contract_text=state["extraction"]["text"],
        selected_skill_texts=state["selected_skill_texts"],
        draft_findings=state.get("draft_findings", []),
        authority_ledger=state.get("authority_ledger", []),
    )
    draft, assignment = models.invoke_structured(
        tier,
        "independent_verifier",
        messages,
        VerificationDraft,
        tools=[TavilySearch(max_results=5)],
    )
    log_model_assignment(assignment)

    return {
        "verification_records": [r.model_dump() for r in draft.verification_records],
        "verifier_newly_identified_findings": [
            f.model_dump() for f in draft.newly_identified_findings
        ],
        "verifier_unsupported_assertions": draft.unsupported_assertions_in_summary,
        "model_assignments": [assignment.model_dump()],
    }
