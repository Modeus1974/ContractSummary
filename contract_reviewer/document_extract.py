"""Dispatches contract text extraction by file extension. See pdf_extract.py and
docx_extract.py for the actual per-format logic; all extractors return the same
{ok, text, pages, warnings, scanned_pages} shape so callers can treat every supported
format identically.
"""
from __future__ import annotations

from pathlib import Path

from contract_reviewer.docx_extract import extract_docx
from contract_reviewer.pdf_extract import extract_pdf

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".md")


def extract_markdown(path: Path) -> dict:
    """Markdown is already plain text -- no parsing needed, just read and wrap it in the
    same shape as the other extractors. Never raises on a bad/unreadable file."""
    result = {"ok": False, "text": "", "pages": [], "warnings": [], "scanned_pages": []}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception as exc:
        result["warnings"].append(f"Could not read Markdown file: {exc}")
        return result

    result["pages"] = [{"page_no": 1, "text": text}]
    result["text"] = f"[Page 1]\n{text}" if text.strip() else ""
    result["ok"] = bool(text.strip())
    if not result["ok"]:
        result["warnings"].append("No extractable text found anywhere in the document.")
    return result


def extract_document(path: Path) -> dict:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".docx":
        return extract_docx(path)
    if suffix == ".md":
        return extract_markdown(path)
    return {
        "ok": False,
        "text": "",
        "pages": [],
        "warnings": [f"Unsupported file type '{suffix}'; expected one of {SUPPORTED_EXTENSIONS}"],
        "scanned_pages": [],
    }
