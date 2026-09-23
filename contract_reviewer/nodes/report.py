"""Stage 5: assemble the Markdown report from reconciled state, write it, and read it
back to verify structural integrity before returning.

Handles both the normal and the Incomplete path through the same template and the same
write+read-back logic, so an Incomplete run still produces a real status report rather
than a fabricated review -- there is no separate "incomplete" node.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from contract_reviewer import io_utils, models, pdf_report
from contract_reviewer.logging_setup import log_model_assignment, log_stage, log_warning
from contract_reviewer.prompts import build_executive_prose_messages
from contract_reviewer.runtime import get_tiers
from contract_reviewer.schemas import ExecutiveAssessment
from contract_reviewer.state import ReviewState

_SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_REQUIRED_HEADINGS = [
    "## 1. Review metadata",
    "## 2. Executive assessment",
    "## 3. Severity-ranked risk register",
    "## 4. Detailed findings",
    "## 5. Actions before signing/performance",
    "## 6. Unverified concerns and limitations",
    "## 7. Authority verification register",
    "## 8. Review coverage and audit summary",
]


def _verification_summary(finding_id: str, verification_records: list[dict]) -> str:
    statuses = [
        r["status"] for r in verification_records if r["finding_id"] == finding_id
    ]
    return ", ".join(statuses) if statuses else "not verified"


def _authority_register_rows(
    authority_ledger: list[dict], verification_records: list[dict]
) -> list[dict]:
    authorities_by_id = {a["authority_id"]: a for a in authority_ledger}
    rows = []
    for rec in verification_records:
        authority = authorities_by_id.get(rec["authority_id"], {})
        rows.append(
            {
                "authority_id": rec["authority_id"],
                "authority_type": authority.get("authority_type", "?"),
                "citation": authority.get("citation"),
                "title": authority.get("title", "?"),
                "finding_id": rec["finding_id"],
                "proposition_checked": rec["proposition_checked"],
                "pinpoint": authority.get("pinpoint", "?"),
                "status": rec["status"],
                "caveats": rec.get("caveats"),
            }
        )
    return rows


def assemble_node(state: ReviewState) -> dict:
    log_stage("assemble")
    incomplete = bool(state.get("incomplete_reason"))
    report_status = (
        "Incomplete" if incomplete else state.get("report_status", "Completed")
    )

    findings = sorted(
        state.get("draft_findings", []),
        key=lambda f: (
            _SEVERITY_ORDER.get(f.get("severity"), 9),
            f.get("finding_id", ""),
        ),
    )
    for f in findings:
        f["verification_summary"] = _verification_summary(
            f["finding_id"], state.get("verification_records", [])
        )

    new_assignments: list[dict] = []
    if incomplete:
        executive_paragraph = (
            f"This review is Incomplete: {state['incomplete_reason']}. "
            "See limitations below for the specific next steps required before a substantive review can proceed."
        )
    else:
        summary_for_prose = {
            "report_status": report_status,
            "commercial_recommendation": state.get("commercial_recommendation"),
            "top_findings": [
                {
                    "finding_id": f["finding_id"],
                    "severity": f["severity"],
                    "consequence": f["consequence"],
                }
                for f in findings[:5]
            ],
            "unresolved_material_disagreement": state.get(
                "unresolved_material_disagreement"
            ),
            "unverified_concerns_count": len(state.get("unverified_concerns", [])),
        }
        tier = get_tiers()["efficient"]
        assessment, assignment = models.invoke_structured(
            tier,
            "report_assembler",
            build_executive_prose_messages(state_summary=summary_for_prose),
            ExecutiveAssessment,
        )
        log_model_assignment(assignment)
        executive_paragraph = assessment.paragraph
        new_assignments = [assignment.model_dump()]

    routing = state.get("routing_record") or {}
    all_assignments = state.get("model_assignments", []) + new_assignments
    context = {
        "run_id": state["run_id"],
        "source_filename": Path(state["source_pdf_path"]).name,
        "source_sha256": state.get("source_sha256"),
        "client_role": state.get("client_role"),
        "client_perspective": state.get("client_perspective"),
        "research_date": state.get("research_date"),
        "selected_skill_paths": list(state.get("selected_skill_texts", {}).keys()),
        "classification_rationale": "; ".join(
            routing.get("substantive_indicators", [])
        ),
        "correction_cycle": state.get("correction_cycle", 0),
        "incomplete_reason": state.get("incomplete_reason"),
        "missing_material": routing.get("unresolved_facts", []),
        "model_assignments": all_assignments,
        "report_status": report_status,
        "commercial_recommendation": state.get("commercial_recommendation"),
        "executive_paragraph": executive_paragraph,
        "findings": findings,
        "actions_before_signing": [
            f["recommended_amendment"]
            for f in findings
            if f.get("severity") in ("Critical", "High")
        ],
        "unverified_concerns": state.get("unverified_concerns", []),
        "authority_register": _authority_register_rows(
            state.get("authority_ledger", []), state.get("verification_records", [])
        ),
        "documents_and_issue_areas_considered": state.get(
            "documents_and_issue_areas_considered", []
        ),
        "areas_with_no_material_finding": state.get(
            "areas_with_no_material_finding", []
        ),
        "scanned_pages": state.get("extraction", {}).get("scanned_pages", []),
        "correction_log": state.get("correction_log", []),
        "errors": state.get("errors", []),
    }

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    rendered = env.get_template("report.md.jinja").render(**context)

    return {
        "final_markdown": rendered,
        "report_context": context,
        "report_status": report_status,
        "model_assignments": new_assignments,
    }


def _validate_report(
    text: str, findings: list[dict], authority_register: list[dict]
) -> list[str]:
    problems = []
    last_pos = -1
    for heading in _REQUIRED_HEADINGS:
        pos = text.find(heading)
        if pos == -1:
            problems.append(f"missing heading: {heading}")
        elif pos < last_pos:
            problems.append(f"heading out of order: {heading}")
        else:
            last_pos = pos

    seen_finding_ids = [f["finding_id"] for f in findings]
    if len(seen_finding_ids) != len(set(seen_finding_ids)):
        problems.append("duplicate finding IDs in draft findings")

    authority_ids = [row["authority_id"] for row in authority_register]
    referenced_authority_ids = {a for f in findings for a in f.get("authority_ids", [])}
    missing_authorities = referenced_authority_ids - set(authority_ids)
    if missing_authorities:
        problems.append(
            f"findings reference authorities missing from the register: {sorted(missing_authorities)}"
        )

    return problems


def write_report_node(state: ReviewState) -> dict:
    log_stage("write_report")
    source_filename = Path(state["source_pdf_path"]).name
    output_path = state.get("output_path_override") or str(
        io_utils.default_report_path(source_filename, state["run_id"])
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(state["final_markdown"], encoding="utf-8", newline="\n")

    read_back = output_path.read_text(encoding="utf-8")
    problems = _validate_report(
        read_back,
        state.get("draft_findings", []),
        _authority_register_rows(
            state.get("authority_ledger", []), state.get("verification_records", [])
        ),
    )

    report_status = state.get("report_status", "Completed")
    if problems:
        for p in problems:
            log_warning(f"report validation: {p}")
        report_status = "Incomplete"

    io_utils.write_artifact(
        state["run_id"], "draft_findings", state.get("draft_findings", [])
    )
    io_utils.write_artifact(
        state["run_id"], "verification_ledger", state.get("verification_records", [])
    )
    io_utils.write_artifact(
        state["run_id"], "correction_log", state.get("correction_log", [])
    )
    io_utils.write_artifact(
        state["run_id"], "model_assignments", state.get("model_assignments", [])
    )
    io_utils.write_artifact(
        state["run_id"],
        "final_state",
        {k: v for k, v in state.items() if k != "final_markdown"},
    )

    pdf_output_path = None
    try:
        pdf_bytes = pdf_report.render_pdf(state.get("report_context", {}))
        pdf_path = Path(io_utils.default_pdf_path(source_filename, state["run_id"]))
        pdf_path.write_bytes(pdf_bytes)
        pdf_output_path = str(pdf_path)
    except Exception as exc:
        # The Markdown report is the authoritative artifact; a PDF-rendering failure is
        # logged but never downgrades report_status -- the review itself is unaffected.
        log_warning(f"PDF rendering failed: {exc}")

    return {
        "output_path": str(output_path),
        "pdf_output_path": pdf_output_path,
        "report_status": report_status,
        "incomplete_reason": (
            (
                state.get("incomplete_reason")
                or "report failed structural read-back validation"
            )
            if problems
            else state.get("incomplete_reason")
        ),
    }
