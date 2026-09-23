"""Builds the compiled LangGraph StateGraph for the contract review workflow."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from contract_reviewer.logging_setup import log_warning
from contract_reviewer.nodes.classify import classify_node, route_after_classify
from contract_reviewer.nodes.factual_check import factual_check_node
from contract_reviewer.nodes.intake import intake_node, route_after_intake
from contract_reviewer.nodes.reconcile import reconcile_node, route_after_reconcile
from contract_reviewer.nodes.report import assemble_node, write_report_node
from contract_reviewer.nodes.review import review_node
from contract_reviewer.nodes.verify import verify_node
from contract_reviewer.state import ReviewState


def _skip_if_incomplete(
    fn: Callable[[ReviewState], dict], stage_name: str
) -> Callable[[ReviewState], dict]:
    """A prior stage already failed permanently -- retrying downstream stages would waste
    calls and risk a misleadingly 'Completed' result, so later stages become no-ops."""

    def wrapped(state: ReviewState) -> dict:
        if state.get("incomplete_reason"):
            return {}
        try:
            return fn(state)
        except Exception as exc:  # transient/permanent model or tool failure
            log_warning(f"{stage_name} failed: {exc}")
            return {
                "errors": [
                    {"stage": stage_name, "kind": "permanent", "detail": str(exc)}
                ],
                "incomplete_reason": f"{stage_name} failed: {exc}",
            }

    return wrapped


def build_graph(checkpoint_db_path: Path):
    graph = StateGraph(ReviewState)

    graph.add_node("intake", intake_node)
    graph.add_node("classify", _skip_if_incomplete(classify_node, "classify"))
    graph.add_node("review", _skip_if_incomplete(review_node, "review"))
    graph.add_node("verify", _skip_if_incomplete(verify_node, "verify"))
    graph.add_node(
        "factual_check", _skip_if_incomplete(factual_check_node, "factual_check")
    )
    graph.add_node("reconcile", reconcile_node)
    graph.add_node("assemble", assemble_node)
    graph.add_node("write_report", write_report_node)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges(
        "intake", route_after_intake, {"classify": "classify", "assemble": "assemble"}
    )
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {"escalate": "classify", "proceed": "review", "incomplete": "assemble"},
    )
    graph.add_edge("review", "verify")
    graph.add_edge("review", "factual_check")
    graph.add_edge("verify", "reconcile")
    graph.add_edge("factual_check", "reconcile")
    graph.add_conditional_edges(
        "reconcile",
        route_after_reconcile,
        {"revise": "review", "assemble": "assemble", "incomplete": "assemble"},
    )
    graph.add_edge("assemble", "write_report")
    graph.add_edge("write_report", END)

    checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(checkpoint_db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return graph.compile(checkpointer=checkpointer)
