"""Stage 1b: classify contract substance and select the applicable skill(s).

Low-confidence classification escalates once from Efficient to Balanced tier; if it is
still low confidence after that, routing proceeds with routing_needs_reviewer_resolution
set, per the spec's "otherwise the allocated legal reviewer resolves it".
"""

from __future__ import annotations

from contract_reviewer import models, prompts, skills
from contract_reviewer.logging_setup import log_model_assignment, log_stage
from contract_reviewer.runtime import get_tiers
from contract_reviewer.schemas import RoutingRecord
from contract_reviewer.state import ReviewState

_TIER_FOR_ATTEMPT = {0: "efficient", 1: "balanced"}


def classify_node(state: ReviewState) -> dict:
    attempt = state.get("classification_attempt", 0)
    tier_name = _TIER_FOR_ATTEMPT.get(attempt, "balanced")
    tier = get_tiers()[tier_name]
    log_stage("classify", f"attempt={attempt} tier={tier_name}")

    skill_files = skills.load_routing_skills()
    messages = prompts.build_classify_messages(
        contract_text=state["extraction"]["text"],
        skill_files=skill_files,
        client_role=state.get("client_role"),
        client_perspective=state.get("client_perspective"),
    )
    routing, assignment = models.invoke_structured(
        tier, "classifier", messages, RoutingRecord
    )
    log_model_assignment(assignment)

    next_attempt = attempt + 1
    selected_texts = skills.skills_by_relative_path(routing.selected_skill_paths)

    return {
        "routing_record": routing.model_dump(),
        "selected_skill_texts": selected_texts,
        "classification_attempt": next_attempt,
        "routing_needs_reviewer_resolution": routing.confidence == "Low"
        and next_attempt >= 2,
        "model_assignments": [assignment.model_dump()],
    }


def route_after_classify(state: ReviewState) -> str:
    routing = state.get("routing_record") or {}
    selected = state.get("selected_skill_texts") or {}
    attempt = state.get("classification_attempt", 0)

    if not selected:
        return "incomplete"
    if routing.get("confidence") == "Low" and attempt < 2:
        return "escalate"
    return "proceed"
