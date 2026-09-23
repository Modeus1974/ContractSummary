"""Stage 4: reconcile verification/factual-check results and enforce the release gate.
Deterministic Python bookkeeping -- no LLM call needed here."""

from __future__ import annotations

from contract_reviewer.logging_setup import log_stage
from contract_reviewer.state import ReviewState


def _records_by_finding(verification_records: list[dict]) -> dict[str, list[dict]]:
    by_finding: dict[str, list[dict]] = {}
    for rec in verification_records:
        by_finding.setdefault(rec["finding_id"], []).append(rec)
    return by_finding


def reconcile_node(state: ReviewState) -> dict:
    if state.get("incomplete_reason"):
        return {"report_status": "Incomplete"}

    cycle = state.get("correction_cycle", 0)
    max_cycles = state.get("max_cycles", 2)
    log_stage("reconcile", f"cycle={cycle}")

    findings = state.get("draft_findings", [])
    verification_records = state.get("verification_records", [])
    factual_notes = state.get("factual_check_notes", [])
    by_finding = _records_by_finding(verification_records)

    defects: list[dict] = []
    unverified_concerns: list[dict] = []

    for f in findings:
        bad = [
            r
            for r in by_finding.get(f["finding_id"], [])
            if r["status"] in ("Unsupported", "Unverified")
        ]
        for r in bad:
            unverified_concerns.append(
                {
                    "finding_id": f["finding_id"],
                    "status": r["status"],
                    "description": f"Authority {r['authority_id']} for proposition "
                    f"'{r['proposition_checked']}': {r['application_check']}",
                }
            )
        if bad and f.get("severity") in ("Critical", "High"):
            defects.append(
                {
                    "finding_id": f["finding_id"],
                    "reason": f"Unresolved authority status for a {f['severity']} finding: {[r['status'] for r in bad]}",
                }
            )

    for note in factual_notes:
        if not note.get("confirmed", True):
            defects.append(
                {"finding_id": note.get("finding_id"), "reason": note["description"]}
            )

    newly_identified = state.get("verifier_newly_identified_findings", [])
    if newly_identified:
        defects.append(
            {
                "finding_id": None,
                "reason": f"Verifier identified {len(newly_identified)} material omitted risk(s) not yet reviewed",
            }
        )

    defects_exist = bool(defects)
    can_revise = defects_exist and cycle < max_cycles
    unresolved_material = defects_exist and not can_revise

    update: dict = {
        "defects_pending": can_revise,
        "unresolved_material_disagreement": unresolved_material,
        "unverified_concerns": unverified_concerns,
    }

    if defects_exist:
        update["correction_log"] = state.get("correction_log", []) + [
            {
                "cycle": cycle + 1,
                "defect_description": "; ".join(
                    d["reason"] for d in defects if d["reason"]
                ),
                "linked_finding_id": None,
                "resolution": "amended" if can_revise else "unresolved",
            }
        ]

    if can_revise:
        update["correction_cycle"] = cycle + 1
        update["revision_brief"] = {
            "defects": defects,
            "newly_identified_findings": newly_identified,
        }
        return update

    if not findings:
        update["report_status"] = "Provisional"
        update["commercial_recommendation"] = "resolve blockers first"
    elif unresolved_material:
        update["report_status"] = "Provisional"
        update["commercial_recommendation"] = (
            "resolve blockers first"
            if any(f.get("severity") == "Critical" for f in findings)
            else "proceed subject to changes"
        )
    else:
        update["report_status"] = "Completed"
        severities = {f.get("severity") for f in findings}
        if "Critical" in severities:
            update["commercial_recommendation"] = "resolve blockers first"
        elif severities & {"High", "Medium"}:
            update["commercial_recommendation"] = "proceed subject to changes"
        else:
            update["commercial_recommendation"] = "proceed"

    return update


def route_after_reconcile(state: ReviewState) -> str:
    if state.get("incomplete_reason"):
        return "incomplete"
    if state.get("defects_pending"):
        return "revise"
    return "assemble"
