"""Stage 1a: read the source document (PDF or Word), hash it, extract text, and record
skill file hashes."""

from __future__ import annotations

from pathlib import Path

from contract_reviewer import document_extract, io_utils, pdf_extract, skills
from contract_reviewer.logging_setup import log_stage, log_warning
from contract_reviewer.state import ReviewState


def intake_node(state: ReviewState) -> dict:
    log_stage("intake", state["source_pdf_path"])
    path = Path(state["source_pdf_path"])

    if not path.is_file():
        log_warning(f"Source file does not exist: {path}")
        return {
            "extraction_ok": False,
            "extraction": {
                "ok": False,
                "text": "",
                "pages": [],
                "warnings": [f"File not found: {path}"],
                "scanned_pages": [],
            },
            "incomplete_reason": f"Source file not found: {path}",
        }

    source_sha256 = pdf_extract.sha256_file(path)
    extraction = document_extract.extract_document(path)

    for warning in extraction["warnings"]:
        log_warning(warning)

    update: dict = {
        "source_sha256": source_sha256,
        "source_filename_safe": io_utils.safe_filename_stem(path.name),
        "extraction": extraction,
        "extraction_ok": extraction["ok"],
        "skill_content_hashes": skills.all_skill_hashes(),
        "classification_attempt": 0,
        "correction_cycle": 0,
    }
    if not extraction["ok"]:
        update["incomplete_reason"] = (
            "Document could not be read or contains no extractable text: "
            + "; ".join(extraction["warnings"])
        )

    io_utils.write_artifact(
        state["run_id"],
        "manifest",
        {
            "source_pdf_path": str(path),
            "source_sha256": source_sha256,
            "extraction_ok": extraction["ok"],
            "warnings": extraction["warnings"],
            "scanned_pages": extraction["scanned_pages"],
            "skill_content_hashes": update["skill_content_hashes"],
        },
    )
    return update


def route_after_intake(state: ReviewState) -> str:
    return "classify" if state.get("extraction_ok") else "assemble"
