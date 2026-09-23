"""Manual check: exercise intake -> classify -> factual_check -> assemble -> write_report
using only Efficient/Balanced-tier calls, skipping the Flagship-tier review/verify stages.

Useful when Flagship-tier (Opus) budget is unavailable but you still want to confirm the
rest of the pipeline works against real model calls. draft_findings/authority_ledger are
seeded by hand (not produced by a real reviewer) since `review` is skipped.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contract_reviewer import config, io_utils, runtime  # noqa: E402
from contract_reviewer.nodes.classify import classify_node  # noqa: E402
from contract_reviewer.nodes.factual_check import factual_check_node  # noqa: E402
from contract_reviewer.nodes.intake import intake_node  # noqa: E402
from contract_reviewer.nodes.report import (
    assemble_node,
    write_report_node,
)  # noqa: E402

SEEDED_FINDINGS = [
    {
        "finding_id": "F001",
        "clause_reference": "Clause 4",
        "clause_text": "the Tenant forfeits the entire security deposit with no right of appeal",
        "affected_party": "Tenant",
        "trigger_scenario": "Tenant terminates early for any reason",
        "consequence": "Total loss of a 3-month deposit regardless of circumstances",
        "severity": "High",
        "confidence": "High",
        "rating_rationale": "Total forfeiture with no proportionality is a severe one-sided term",
        "legal_proposition": "A forfeiture clause operating as an unconscionable penalty rather "
        "than a genuine pre-estimate of loss may not be enforced as drafted",
        "authority_ids": ["A001"],
        "recommended_amendment": "Cap forfeiture at actual loss suffered",
        "fallback_position": "Pro-rate forfeiture by month",
        "residual_risk": "None if amended",
        "status": "open",
    }
]
SEEDED_AUTHORITIES = [
    {
        "authority_id": "A001",
        "authority_type": "case",
        "title": "Denka Advantech Pte Ltd and another v Seraya Energy Pte Ltd and another and other appeals",
        "citation": "[2020] SGCA 119",
        "url": "https://www.elitigation.sg/gd/s/2020_SGCA_119",
        "pinpoint": "see the Court's discussion of penalty clauses",
        "application_notes": "Seeded by this check script (not produced by a real reviewer call) "
        "-- review is skipped here to avoid Flagship-tier cost.",
    }
]


def main() -> int:
    config.load_env()
    runtime.set_tiers(config.load_tier_config())

    state = {
        "run_id": io_utils.new_run_id(),
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_pdf_path": str(
            Path(__file__).resolve().parent / "fixtures" / "sample_tenancy.pdf"
        ),
        "client_role": "tenant",
        "client_perspective": None,
        "research_date": datetime.now(timezone.utc).date().isoformat(),
        "max_cycles": 2,
        "output_path_override": None,
        "model_assignments": [],
        "errors": [],
    }

    print("== intake ==")
    state.update(intake_node(state))
    print("extraction_ok:", state.get("extraction_ok"))
    if not state.get("extraction_ok"):
        print("FAIL: extraction failed")
        return 1

    print("== classify (Efficient/Balanced) ==")
    state.update(classify_node(state))
    print("routing_record:", state["routing_record"])

    print("== (review skipped -- seeding findings/authorities by hand) ==")
    state["draft_findings"] = SEEDED_FINDINGS
    state["authority_ledger"] = SEEDED_AUTHORITIES
    state["correction_cycle"] = 0

    print("== factual_check (Balanced) ==")
    state.update(factual_check_node(state))
    print("factual_check_notes:", state["factual_check_notes"])

    print("== (verify/reconcile skipped -- setting status by hand) ==")
    state["verification_records"] = []
    state["unverified_concerns"] = []
    state["correction_log"] = []
    state["report_status"] = "Provisional"
    state["commercial_recommendation"] = "proceed subject to changes"
    state["unresolved_material_disagreement"] = True

    print("== assemble (Efficient) ==")
    state.update(assemble_node(state))

    print("== write_report ==")
    state.update(write_report_node(state))

    print("\nOutput path:", state["output_path"])
    print("Report status:", state["report_status"])
    print("Model assignments used:")
    for a in state["model_assignments"]:
        print(" ", a)

    return 0


if __name__ == "__main__":
    sys.exit(main())
