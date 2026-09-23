"""Stage 3b: quotation/coverage/consistency checks. Deterministic substring verification
runs first in code; an LLM call only handles the harder semantic checks."""

from __future__ import annotations

from pydantic import BaseModel

from contract_reviewer import models, prompts
from contract_reviewer.logging_setup import log_model_assignment, log_stage
from contract_reviewer.runtime import get_tiers
from contract_reviewer.schemas import FactualCheckNote
from contract_reviewer.state import ReviewState


class _FactualCheckDraft(BaseModel):
    notes: list[FactualCheckNote]


def _substring_issues(contract_text: str, findings: list[dict]) -> list[dict]:
    issues = []
    for f in findings:
        quote = (f.get("clause_text") or "").strip()
        if quote and quote not in contract_text:
            issues.append(
                {
                    "finding_id": f.get("finding_id"),
                    "issue": "quotation not found verbatim in extracted source text",
                }
            )
    return issues


def factual_check_node(state: ReviewState) -> dict:
    log_stage("factual_check")
    tier = get_tiers()["balanced"]

    findings = state.get("draft_findings", [])
    substring_issues = _substring_issues(state["extraction"]["text"], findings)

    messages = prompts.build_factual_check_messages(
        contract_text=state["extraction"]["text"],
        draft_findings=findings,
        substring_issues=substring_issues,
    )
    draft, assignment = models.invoke_structured(
        tier, "factual_checker", messages, _FactualCheckDraft
    )
    log_model_assignment(assignment)

    notes = [n.model_dump() for n in draft.notes]
    for issue in substring_issues:
        notes.append(
            {
                "finding_id": issue["finding_id"],
                "category": "quotation",
                "description": issue["issue"],
                "confirmed": False,
            }
        )

    return {
        "factual_check_notes": notes,
        "model_assignments": [assignment.model_dump()],
    }
